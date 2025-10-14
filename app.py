import os
import pandas as pd
import io
import json
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort, Response, stream_with_context, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func, desc, asc
from datetime import datetime, timedelta, date
from openai import OpenAI
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from dotenv import load_dotenv
from functools import wraps
from urllib.parse import urlencode

load_dotenv()

# --- 基本配置 ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_default_fallback_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'library.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
app.config['ALLOWED_EXCEL_EXTENSIONS'] = {'xlsx'}

# --- AI & Speech API 配置 ---
AI_DETAILS_API_KEY = os.getenv("AI_DETAILS_API_KEY")
details_client = OpenAI(api_key=AI_DETAILS_API_KEY, base_url="https://api.deepseek.com")
AI_SEARCH_API_KEY = os.getenv("AI_SEARCH_API_KEY")
search_client = OpenAI(api_key=AI_SEARCH_API_KEY, base_url="https://api.deepseek.com")
WORD_VECTOR_API_KEY = os.getenv("WORD_VECTOR_API_KEY")
vector_client = OpenAI(api_key=WORD_VECTOR_API_KEY, base_url="https://api.deepseek.com")
BAIDU_APP_ID = os.getenv("BAIDU_SPEECH_APP_ID")
BAIDU_API_KEY = os.getenv("BAIDU_SPEECH_API_KEY")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SPEECH_SECRET_KEY")

# --- RAG & Baidu Token Cache ---
vectorizer, book_vectors, book_corpus_data = None, None, []
baidu_token_cache = {'token': None, 'expires_at': 0}


def is_allowed_excel_file(file_storage):
    """Validate uploaded Excel files using both extension and mimetype checks."""
    if not file_storage or not file_storage.filename:
        return False

    filename = secure_filename(file_storage.filename)
    if '.' not in filename:
        return False

    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in app.config['ALLOWED_EXCEL_EXTENSIONS']:
        return False

    mimetype = (file_storage.mimetype or '').lower()
    if mimetype and all(token not in mimetype for token in ['sheet', 'excel']) and mimetype != 'application/octet-stream':
        return False

    return True

# --- 数据库和登录管理器初始化 ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录以访问此页面。'
login_manager.login_message_category = 'info'


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(self), microphone=(), geolocation=()')

    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'self'"
    )
    response.headers.setdefault('Content-Security-Policy', csp)

    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

    return response


@app.context_processor
def inject_current_year(): return {'current_year': datetime.utcnow().year}

# --- 数据库模型定义 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='faculty') 
    records = db.relationship('BorrowRecord', backref='borrower', lazy=True, cascade="all, delete-orphan")
    wants = db.relationship('Want', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    api_usages = db.relationship('ApiUsage', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def has_wanted(self, book): return self.wants.filter_by(book_id=book.id).count() > 0

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    publisher = db.Column(db.String(200), nullable=True)
    bookshelf_number = db.Column(db.String(50), nullable=True, index=True)
    isbn = db.Column(db.String(20), nullable=False, index=True)  # 移除unique约束
    book_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    stock = db.Column(db.Integer, default=1)
    quantity_available = db.Column(db.Integer, default=1)
    records = db.relationship('BorrowRecord', backref='book', lazy=True, cascade="all, delete-orphan")

class BorrowRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=30))
    return_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default='borrowed')

class Want(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class ApiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    api_name = db.Column(db.String(50), nullable=False)
    usage_date = db.Column(db.Date, nullable=False, default=date.today)
    count = db.Column(db.Integer, default=0)
    __table_args__ = (db.UniqueConstraint('user_id', 'api_name', 'usage_date', name='_user_api_date_uc'),)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def chinese_tokenizer(text):
    return jieba.lcut(text)

# --- API 用量限制装饰器 ---
def limit_api_usage(api_name, limit=15):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.is_anonymous or current_user.role == 'admin':
                return f(*args, **kwargs)
            today = date.today()
            usage = current_user.api_usages.filter_by(api_name=api_name, usage_date=today).first()
            if usage and usage.count >= limit:
                return jsonify({'error': f'您今日的"{api_name}"服务调用次数已达上限。'}), 429
            if not usage:
                usage = ApiUsage(user_id=current_user.id, api_name=api_name, usage_date=today, count=1)
                db.session.add(usage)
            else:
                usage.count += 1
            db.session.commit()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- 百度语音服务 ---
def get_baidu_token():
    now = time.time()
    if baidu_token_cache['token'] and baidu_token_cache['expires_at'] > now:
        return baidu_token_cache['token']
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": BAIDU_API_KEY, "client_secret": BAIDU_SECRET_KEY}
    response = requests.post(url, params=params)
    if response.status_code == 200:
        data = response.json()
        baidu_token_cache['token'] = data.get("access_token")
        baidu_token_cache['expires_at'] = now + data.get("expires_in", 3600) - 60
        return baidu_token_cache['token']
    return None

# --- 搜索建议API ---
@app.route('/search-suggestions')
@login_required
def search_suggestions():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 1:
        return jsonify([])
    
    # 搜索书名和编码
    books = Book.query.filter(
        or_(
            Book.title.ilike(f"%{query}%"),
            Book.book_code.ilike(f"%{query}%"),
            Book.publisher.ilike(f"%{query}%")
        )
    ).limit(10).all()
    
    suggestions = []
    seen = set()
    
    for book in books:
        # 书名建议
        if book.title not in seen:
            suggestions.append({
                'text': book.title,
                'type': 'title',
                'icon': 'book'
            })
            seen.add(book.title)
        
        # 编码建议
        if book.book_code not in seen:
            suggestions.append({
                'text': book.book_code,
                'type': 'code',
                'icon': 'code'
            })
            seen.add(book.book_code)
    
    return jsonify(suggestions[:8])

# --- 所有路由 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('admin_dashboard' if current_user.role == 'admin' else 'index'))
    if request.method == 'POST':
        login_type, username, password = request.form.get('type'), request.form.get('username'), request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and ((login_type == 'admin' and user.role == 'admin') or (login_type == 'faculty' and user.role == 'faculty')):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'index'))
        else: flash('用户名、密码或登录类型错误。', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出登录。', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    if current_user.role == 'admin': return redirect(url_for('admin_dashboard'))
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '')
    sort_by = request.args.get('sort_by', 'id')
    sort_order = request.args.get('sort_order', 'desc')
    
    query = Book.query
    if search_query: 
        query = query.filter(or_(
            Book.title.ilike(f"%{search_query}%"), 
            Book.book_code.ilike(f"%{search_query}%"),
            Book.publisher.ilike(f"%{search_query}%"),
            Book.bookshelf_number.ilike(f"%{search_query}%")
        ))
    
    # 排序逻辑
    sort_column = getattr(Book, sort_by, Book.id)
    if sort_order == 'desc':
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    books_pagination = query.paginate(page=page, per_page=10, error_out=False)
    return render_template('index.html', books_pagination=books_pagination, search_query=search_query, sort_by=sort_by, sort_order=sort_order)

@app.route('/my-records')
@login_required
def my_records():
    if current_user.role != 'faculty': abort(403)
    page = request.args.get('page', 1, type=int)
    borrowed_count = BorrowRecord.query.filter_by(user_id=current_user.id, status='borrowed').count()
    all_records_pagination = BorrowRecord.query.filter_by(user_id=current_user.id).order_by(BorrowRecord.borrow_date.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template('records.html', records_pagination=all_records_pagination, borrowed_count=borrowed_count)

@app.route('/borrow/<int:book_id>', methods=['POST'])
@login_required
def borrow_book(book_id):
    if current_user.role != 'faculty': abort(403)
    book = Book.query.get_or_404(book_id)
    existing_loan = BorrowRecord.query.filter_by(user_id=current_user.id, book_id=book.id, status='borrowed').first()
    if existing_loan:
        flash(f'您已借阅《{book.title}》，无法重复借阅。', 'warning')
    elif book.quantity_available <= 0:
        flash('该书已无库存可借。', 'warning')
    else:
        book.quantity_available -= 1
        db.session.add(BorrowRecord(user_id=current_user.id, book_id=book.id))
        db.session.commit()
        flash(f'成功借阅《{book.title}》。', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/borrow-by-code/<string:book_code>', methods=['POST'])
@login_required
def borrow_by_code(book_code):
    if current_user.role != 'faculty': return jsonify({'success': False, 'message': '权限不足'}), 403
    book = Book.query.filter_by(book_code=book_code).first()
    if not book: return jsonify({'success': False, 'message': '未找到该书'}), 404
    existing_loan = BorrowRecord.query.filter_by(user_id=current_user.id, book_id=book.id, status='borrowed').first()
    if existing_loan: return jsonify({'success': False, 'message': f'您已借阅《{book.title}》'})
    if book.quantity_available <= 0: return jsonify({'success': False, 'message': '该书已无库存'})
    book.quantity_available -= 1
    db.session.add(BorrowRecord(user_id=current_user.id, book_id=book.id))
    db.session.commit()
    return jsonify({'success': True, 'message': f'成功借阅《{book.title}》'})


@app.route('/return-by-code/<string:book_code>', methods=['POST'])
@login_required
def return_by_code(book_code):
    if current_user.role != 'faculty':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    record = (
        BorrowRecord.query
        .join(Book)
        .filter(
            BorrowRecord.user_id == current_user.id,
            BorrowRecord.status == 'borrowed',
            Book.book_code == book_code
        )
        .first()
    )

    if not record:
        return jsonify({'success': False, 'message': '未找到与该编码匹配的在借记录'}), 404

    record.status = 'returned'
    record.return_date = datetime.utcnow()
    record.book.quantity_available += 1
    db.session.commit()

    return jsonify({'success': True, 'message': f'成功归还《{record.book.title}》'})

@app.route('/want/<int:book_id>', methods=['POST'])
@login_required
def want_book(book_id):
    if current_user.role != 'faculty': abort(403)
    book = Book.query.get_or_404(book_id)
    if not current_user.has_wanted(book):
        db.session.add(Want(user_id=current_user.id, book_id=book.id))
        db.session.commit()
        flash(f'已将《{book.title}》加入您的想读列表。', 'success')
    else: flash(f'《{book.title}》已在您的想读列表中。', 'info')
    return redirect(request.referrer or url_for('index'))

@app.route('/return/<int:record_id>', methods=['POST'])
@login_required
def return_book(record_id):
    if current_user.role != 'faculty': abort(403)
    record = BorrowRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id: abort(403)
    if record.status == 'borrowed':
        record.status, record.return_date = 'returned', datetime.utcnow()
        record.book.quantity_available += 1
        db.session.commit()
        flash(f'成功归还《{record.book.title}》。', 'success')
    else: flash('该记录状态异常，无法归还。', 'warning')
    return redirect(url_for('my_records'))

@app.route('/return-all', methods=['POST'])
@login_required
def return_all_books():
    if current_user.role != 'faculty': abort(403)
    records_to_return = BorrowRecord.query.filter_by(user_id=current_user.id, status='borrowed').all()
    if not records_to_return: flash('没有需要归还的书籍。', 'info')
    else:
        for record in records_to_return:
            record.status, record.return_date = 'returned', datetime.utcnow()
            record.book.quantity_available += 1
        db.session.commit()
        flash(f'成功归还 {len(records_to_return)} 本书籍。', 'success')
    return redirect(url_for('my_records'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role != 'faculty': abort(403)
    if request.method == 'POST':
        old_password, new_password, confirm_password = request.form.get('old_password'), request.form.get('new_password'), request.form.get('confirm_password')
        if not current_user.check_password(old_password): flash('当前密码不正确。', 'danger')
        elif new_password != confirm_password: flash('两次输入的新密码不一致。', 'danger')
        elif len(new_password) < 4: flash('新密码长度不能少于4位。', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            logout_user()
            flash('密码修改成功，请重新登录。', 'success')
            return redirect(url_for('login'))
    return render_template('profile.html')

@app.route('/ask-ai', methods=['POST'])
@login_required
@limit_api_usage('AI问答')
def ask_ai():
    data = request.get_json()
    chat_history = data.get('history', [])
    if not chat_history: return Response(json.dumps({'error': 'History is empty'}), status=400, mimetype='application/json')
    def generate():
        try:
            stream = details_client.chat.completions.create(model="deepseek-chat", messages=chat_history, stream=True)
            for chunk in stream:
                if content := chunk.choices[0].delta.content: yield content
        except Exception as e:
            print(f"AI Details API Error: {e}")
            yield "抱歉，图书详情AI服务暂时无法连接。"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/ai-search', methods=['POST'])
@login_required
@limit_api_usage('AI搜书')
def ai_search():
    data = request.get_json()
    user_query = data.get('query')
    expanded_query = data.get('expanded_query')
    if not user_query: return Response(json.dumps({'error': 'Query is empty'}), status=400, mimetype='application/json')
    if vectorizer is None or book_vectors is None: return Response(json.dumps({'error': 'AI Search engine not initialized.'}), status=503)
    final_query = expanded_query if expanded_query else user_query
    query_vector = vectorizer.transform([final_query])
    similarities = cosine_similarity(query_vector, book_vectors).flatten()
    top_n_indices = np.argsort(similarities)[-5:][::-1]
    retrieved_context = [f"- 书名:《{book['title']}》, 作者:{book['publisher']}, ISBN:{book['isbn']}, 状态:{'可用' if book['quantity_available'] > 0 else '已借出'}, 图书编码:{book['book_code']}" for index in top_n_indices if similarities[index] > 0.01 and (book := book_corpus_data[index])]
    context_str = "\n".join(retrieved_context) if retrieved_context else "未在书库中找到直接相关的书籍。"
    system_prompt = f"""你是一个专业的图书查询助手。请严格根据下面提供的"相关书籍资料"来回答用户的问题。
相关书籍资料:
---
{context_str}
---
请根据以上资料，回答用户的问题："{user_query}"。如果资料中有合适的书籍，请推荐给用户并简要说明理由。如果资料显示未找到相关书籍，请如实告知用户。请保持回答简洁。"""
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_query}]
    def generate():
        try:
            stream = search_client.chat.completions.create(model="deepseek-chat", messages=messages, stream=True)
            for chunk in stream:
                if content := chunk.choices[0].delta.content: yield content
        except Exception as e:
            print(f"AI Search API Error: {e}")
            yield "抱歉，AI搜书服务在生成回答时遇到问题。"
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/ai-expand-query', methods=['POST'])
@login_required
@limit_api_usage('AI语义扩展')
def ai_expand_query():
    data = request.get_json()
    query = data.get('query', '').strip()
    if not query: return jsonify({'success': False, 'message': 'Query is empty'}), 400
    system_prompt = """你是一个专为图书馆检索系统服务的、高效的语义解析引擎。你的唯一任务是将用户的自然语言查询，严格地转换为一个结构化的JSON对象，以便后续的关键词匹配。严格遵守以下处理规则：
1. 核心实体识别: 识别查询中的核心概念，如人物、事件、主题、作品等。
2. 同义词/近义词扩展: 为核心实体提供2-3个最相关的同义或近义词。
3. 时间范围解析: 如果查询中包含时期描述（如"维多利亚时期"、"明末清初"），将其解析为一个大致的年份范围（如 "1837-1901"）。
4. 生成上位/下位概念: 为核心主题生成1个更宽泛的父概念（如"英国文学"）和1-2个更具体的子概念（如"工业小说"）。
5. 补充学术关键词: 基于查询意图，补充3-5个最可能相关的学术关键词（比如：相关作家、学者、作品、理论、术语和学术关键词）。
输出格式: 必须严格返回一个JSON对象。"""
    try:
        response = vector_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}], response_format={"type": "json_object"})
        expanded_data = json.loads(response.choices[0].message.content)
        print("\n--- Word_Vector API Response ---")
        print(json.dumps(expanded_data, indent=2, ensure_ascii=False))
        print("----------------------------\n")
        all_terms = set()
        def extract_terms(data):
            if isinstance(data, dict):
                for key, value in data.items():
                    extract_terms(value)
            elif isinstance(data, list):
                for item in data:
                    extract_terms(item)
            elif isinstance(data, str):
                all_terms.add(data)
        extract_terms(expanded_data)
        return jsonify({'success': True, 'expanded_query': " ".join(all_terms)})
    except Exception as e:
        print(f"AI Query Expansion Error: {e}")
        return jsonify({'success': False, 'message': 'AI查询扩展失败'}), 500

@app.route('/ai-recommend', methods=['POST'])
@login_required
def ai_recommend():
    data = request.get_json()
    query = data.get('query', '').strip()
    if not query: return jsonify({'success': False, 'message': 'Query is empty'}), 400
    if vectorizer is None or book_vectors is None: return jsonify({'success': False, 'message': 'RAG engine not ready'}), 503
    query_vector = vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, book_vectors).flatten()
    top_n_indices = np.argsort(similarities)[-5:][::-1]
    recommendations = [{'title': book_corpus_data[i]['title'], 'code': book_corpus_data[i]['book_code']} for i in top_n_indices if similarities[i] > 0.01 and book_corpus_data[i]['quantity_available'] > 0]
    return jsonify({'success': True, 'recommendations': recommendations})

@app.route('/text-to-speech', methods=['POST'])
@login_required
@limit_api_usage('语音合成')
def text_to_speech():
    text = request.json.get('text', '')
    if not text: return jsonify({'error': 'No text provided'}), 400
    token = get_baidu_token()
    if not token: return jsonify({'error': 'Could not get access token'}), 500
    payload = {
        'tex': text,  # 直接使用文本
        'tok': token, 
        'cuid': current_user.username, 
        'ctp': 1, 
        'lan': 'zh', 
        'spd': 5, 
        'pit': 5, 
        'vol': 9, 
        'per': 4226, 
        'aue': 3
    }
    
    response = requests.post("https://tsn.baidu.com/text2audio", data=payload)
    
    if response.headers.get("Content-Type") == "audio/mp3":
        return Response(response.content, mimetype='audio/mp3')
    else:
        return jsonify(response.json()), response.status_code

# --- 管理员路由 ---
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': abort(403)
    books = Book.query.order_by(Book.id.desc()).all()
    faculty_users = User.query.filter_by(role='faculty').order_by(User.id).all()
    wants_query = db.session.query(Book.title, func.count(Want.id).label('want_count')).join(Want).group_by(Book.title).order_by(func.count(Want.id).desc()).all()
    filters = {'name': request.args.get('name', ''), 'start_date': request.args.get('start_date', ''), 'end_date': request.args.get('end_date', ''), 'status': request.args.get('status', 'all')}
    query = BorrowRecord.query.join(User).join(Book)
    if filters['name']: query = query.filter(User.full_name.ilike(f"%{filters['name']}%"))
    if filters['start_date']: query = query.filter(BorrowRecord.borrow_date >= datetime.strptime(filters['start_date'], '%Y-%m-%d'))
    if filters['end_date']: query = query.filter(BorrowRecord.borrow_date < (datetime.strptime(filters['end_date'], '%Y-%m-%d') + timedelta(days=1)))
    if filters['status'] != 'all': query = query.filter(BorrowRecord.status == filters['status'])
    page = request.args.get('page', 1, type=int)
    records_pagination = query.order_by(BorrowRecord.borrow_date.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template('admin_dashboard.html', books=books, faculty_users=faculty_users, wants_list=wants_query, records_pagination=records_pagination, filters=filters)

@app.route('/admin/update-ai-catalog', methods=['POST'])
@login_required
def update_ai_catalog():
    if current_user.role != 'admin': abort(403)
    try:
        global vectorizer, book_vectors, book_corpus_data
        all_books = Book.query.all()
        if not all_books:
            flash('书库为空，无法更新AI目录。', 'warning')
            return redirect(url_for('admin_dashboard'))
        corpus = [f"{b.title} {b.publisher} {b.bookshelf_number}" for b in all_books]
        book_corpus_data = [{'title': b.title, 'publisher': b.publisher, 'isbn': b.isbn, 'book_code': b.book_code, 'quantity_available': b.quantity_available, 'bookshelf_number': b.bookshelf_number} for b in all_books]
        vectorizer = TfidfVectorizer(tokenizer=chinese_tokenizer)
        book_vectors = vectorizer.fit_transform(corpus)
        flash(f'AI检索引擎更新成功！共索引 {len(all_books)} 本书。', 'success')
    except Exception as e:
        flash(f'更新AI检索引擎时发生错误: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/import-books', methods=['POST'])
@login_required
def import_books():
    if current_user.role != 'admin': abort(403)
    file = request.files.get('book_file')
    upload_mode = request.form.get('upload_mode', 'append')

    if not file or file.filename == '':
        flash('未选择任何文件。', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not is_allowed_excel_file(file):
        flash('请上传受支持的 .xlsx 格式文件。', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        if upload_mode == 'overwrite':
            db.session.query(BorrowRecord).delete()
            db.session.query(Want).delete()
            db.session.query(Book).delete()
            db.session.commit()
            flash('已清空现有书库，正在导入新数据...', 'info')

        df = pd.read_excel(file)
        required_columns = {'书名', '出版社', 'ISBN', '编码', '库存量', '书柜号'}
        if not required_columns.issubset(df.columns):
            flash(f'Excel文件必须包含以下列: {", ".join(required_columns)}', 'danger')
            return redirect(url_for('admin_dashboard'))

        added_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            book_code, isbn = str(row['编码']).strip(), str(row['ISBN']).strip()

            try:
                stock = int(row['库存量'])
            except (ValueError, TypeError):
                skipped_count += 1
                continue

            existing_book = Book.query.filter_by(book_code=book_code).first()

            if not existing_book:
                db.session.add(Book(
                    title=row['书名'],
                    publisher=row['出版社'],
                    isbn=isbn,
                    book_code=book_code,
                    stock=stock,
                    quantity_available=stock,
                    bookshelf_number=row.get('书柜号')
                ))
                added_count += 1
            else:
                skipped_count += 1

        db.session.commit()
        flash(f'数据导入完成！新增 {added_count} 本书，跳过 {skipped_count} 本重复编码的书。', 'success')
        update_ai_catalog_on_startup()
        flash('AI检索引擎已同步更新。', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'导入失败: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/import-users', methods=['POST'])
@login_required
def admin_import_users():
    if current_user.role != 'admin':
        abort(403)

    file = request.files.get('user_file')
    if not file or file.filename == '':
        flash('未选择任何用户数据文件。', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not is_allowed_excel_file(file):
        flash('请上传受支持的 .xlsx 格式用户文件。', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        df = pd.read_excel(file)
    except Exception as exc:
        flash(f'无法读取上传的用户文件: {exc}', 'danger')
        return redirect(url_for('admin_dashboard'))

    required_sets = [
        {'工号', '教职工姓名', '初始密码'},
        {'工号', '教职工姓名', '身份证后四位'}
    ]

    if not any(columns.issubset(df.columns) for columns in required_sets):
        flash('Excel文件必须包含「工号」「教职工姓名」以及「初始密码」或「身份证后四位」列。', 'danger')
        return redirect(url_for('admin_dashboard'))

    password_column = '初始密码' if '初始密码' in df.columns else '身份证后四位'

    added, skipped = 0, 0

    for _, row in df.iterrows():
        username = str(row.get('工号', '')).strip()
        full_name = str(row.get('教职工姓名', '')).strip() or username
        raw_password = row.get(password_column)

        password = None
        if pd.isna(raw_password):
            password = None
        elif isinstance(raw_password, float):
            if raw_password.is_integer():
                password = str(int(raw_password))
            else:
                password = str(raw_password)
        elif isinstance(raw_password, (int, np.integer)):
            password = str(raw_password)
        elif isinstance(raw_password, str):
            password = raw_password.strip()

        if password:
            password = password.strip()
            if password.lower() == 'nan':
                password = None

        if not username or not password:
            skipped += 1
            continue

        if User.query.filter_by(username=username).first():
            skipped += 1
            continue

        new_user = User(
            username=username,
            full_name=full_name,
            role='faculty',
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        added += 1

    if added:
        db.session.commit()
        flash(f'成功导入 {added} 位新用户，跳过 {skipped} 条记录。', 'success')
    else:
        db.session.rollback()
        flash(f'没有导入新的用户，跳过 {skipped} 条记录。', 'warning')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/return', methods=['POST'])
@login_required
def admin_return_book():
    if current_user.role != 'admin': abort(403)
    book_code = request.form.get('book_code')
    record = BorrowRecord.query.join(Book).filter(Book.book_code == book_code, BorrowRecord.status == 'borrowed').first()
    if not record: flash('未找到该图书编码对应的已借出记录。', 'danger')
    else:
        record.status, record.return_date = 'returned', datetime.utcnow()
        record.book.quantity_available += 1
        db.session.commit()
        flash(f'《{record.book.title}》已成功归还。', 'success')
    return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/book/add', methods=['POST'])
@login_required
def admin_add_book():
    if current_user.role != 'admin': abort(403)
    data = request.form
    if Book.query.filter_by(book_code=data['book_code']).first():
        flash('图书编码已存在。', 'danger')
    else:
        new_book = Book(title=data['title'], publisher=data['publisher'], isbn=data['isbn'], book_code=data['book_code'], stock=int(data['stock']), quantity_available=int(data['stock']), bookshelf_number=data.get('bookshelf_number'))
        db.session.add(new_book)
        db.session.commit()
        flash(f'书籍《{new_book.title}》添加成功。', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/book/update/<int:book_id>', methods=['POST'])
@login_required
def admin_update_book(book_id):
    if current_user.role != 'admin': abort(403)
    book = Book.query.get_or_404(book_id)
    data = request.form
    stock_change = int(data['stock']) - book.stock
    book.title, book.publisher, book.isbn, book.book_code, book.stock, book.bookshelf_number = data['title'], data['publisher'], data['isbn'], data['book_code'], int(data['stock']), data.get('bookshelf_number')
    book.quantity_available += stock_change
    db.session.commit()
    flash(f'书籍《{book.title}》信息更新成功。', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/book/delete/<int:book_id>', methods=['POST'])
@login_required
def admin_delete_book(book_id):
    if current_user.role != 'admin': abort(403)
    book = Book.query.get_or_404(book_id)
    flash(f'书籍《{book.title}》已删除。', 'success')
    db.session.delete(book)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/add', methods=['POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin': abort(403)
    username, full_name, password = request.form.get('username'), request.form.get('full_name'), request.form.get('password')
    if not all([username, full_name, password]): flash('所有字段均为必填项。', 'danger')
    elif User.query.filter_by(username=username).first(): flash('该工号已被注册。', 'danger')
    else:
        db.session.add(User(username=username, full_name=full_name, role='faculty', password_hash=generate_password_hash(password)))
        db.session.commit()
        flash(f'用户 {full_name} ({username}) 添加成功。', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/update/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user(user_id):
    if current_user.role != 'admin': abort(403)
    user = User.query.get_or_404(user_id)
    user.full_name = request.form.get('full_name')
    if new_password := request.form.get('password'):
        user.set_password(new_password)
        flash(f'用户 {user.full_name} 的姓名和密码已更新。', 'success')
    else:
        flash(f'用户 {user.full_name} 的姓名已更新。', 'success')
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin': abort(403)
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('不能删除管理员账户。', 'danger')
        return redirect(url_for('admin_dashboard'))
    flash(f'用户 {user.full_name} ({user.username}) 已被成功删除。', 'success')
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/export-records')
@login_required
def admin_export_records():
    if current_user.role != 'admin': abort(403)
    filters = {'name': request.args.get('name', ''), 'start_date': request.args.get('start_date', ''), 'end_date': request.args.get('end_date', ''), 'status': request.args.get('status', 'all')}
    query = BorrowRecord.query.join(User).join(Book)
    if filters['name']: query = query.filter(User.full_name.ilike(f"%{filters['name']}%"))
    if filters['start_date']: query = query.filter(BorrowRecord.borrow_date >= datetime.strptime(filters['start_date'], '%Y-%m-%d'))
    if filters['end_date']: query = query.filter(BorrowRecord.borrow_date < (datetime.strptime(filters['end_date'], '%Y-%m-%d') + timedelta(days=1)))
    if filters['status'] != 'all': query = query.filter(BorrowRecord.status == filters['status'])
    records = query.order_by(BorrowRecord.borrow_date.desc()).all()
    data = [{'书名': r.book.title, '图书编码': r.book.book_code, '借阅人': r.borrower.full_name, '工号': r.borrower.username, '借阅日期': r.borrow_date.strftime('%Y-%m-%d %H:%M'), '应还日期': r.due_date.strftime('%Y-%m-%d'), '归还日期': r.return_date.strftime('%Y-%m-%d %H:%M') if r.return_date else '未归还', '状态': '已归还' if r.status == 'returned' else '借阅中'} for r in records]
    df, output = pd.DataFrame(data), io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='借阅记录')
    output.seek(0)
    filename = f"borrow_records_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return Response(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment;filename={filename}"})

# --- 应用初始化函数 ---
def init_database():
    with app.app_context():
        db.create_all()
        admin_pass = os.getenv("ADMIN_PASSWORD", "Admin")
        if not User.query.filter_by(username='Admin').first():
            db.session.add(User(username='Admin', full_name='系统管理员', role='admin', password_hash=generate_password_hash(admin_pass)))
            print("Admin user created.")
        
        try:
            user_file = os.path.join(basedir, '账密.xlsx')
            if os.path.exists(user_file):
                df_users = pd.read_excel(user_file)
                for _, row in df_users.iterrows():
                    username = str(row['工号'])
                    if not User.query.filter_by(username=username).first():
                        db.session.add(User(username=username, full_name=row.get('教职工姓名', username), role='faculty', password_hash=generate_password_hash(str(row['身份证后四位']))))
                print(f"Imported users from 账密.xlsx")
        except FileNotFoundError:
            print("Warning: '账密.xlsx' not found. Creating fallback user if defined.")
            fallback_user_data = os.getenv("FALLBACK_FACULTY_USER")
            if fallback_user_data:
                try:
                    username, full_name, password = fallback_user_data.split(',')
                    if not User.query.filter_by(username=username).first():
                        db.session.add(User(username=username, full_name=full_name, role='faculty', password_hash=generate_password_hash(password)))
                        print(f"Created fallback faculty user: {username}")
                except Exception as e:
                    print(f"Error parsing FALLBACK_FACULTY_USER: {e}")

        except Exception as e:
            print(f"Error importing users: {e}")
        
        db.session.commit()
        print("Initializing AI Catalog for the first time...")
        with app.test_request_context():
            update_ai_catalog_on_startup()

def update_ai_catalog_on_startup():
    try:
        global vectorizer, book_vectors, book_corpus_data
        all_books = Book.query.all()
        if not all_books: 
            print("No books in DB, AI engine not initialized.")
            return
        corpus = [f"{b.title} {b.publisher} {b.bookshelf_number}" for b in all_books]
        book_corpus_data = [{'title': b.title, 'publisher': b.publisher, 'isbn': b.isbn, 'book_code': b.book_code, 'quantity_available': b.quantity_available, 'bookshelf_number': b.bookshelf_number} for b in all_books]
        vectorizer = TfidfVectorizer(tokenizer=chinese_tokenizer)
        book_vectors = vectorizer.fit_transform(corpus)
        print(f'AI Search Engine initialized with {len(all_books)} books.')
    except Exception as e:
        print(f"Failed to initialize AI Search Engine: {e}")

# --- 主程序入口 ---
if __name__ == '__main__':
    init_database()
    if not all([AI_DETAILS_API_KEY, AI_SEARCH_API_KEY, WORD_VECTOR_API_KEY, BAIDU_API_KEY, BAIDU_SECRET_KEY]):
        print("\n\033[91m错误: 缺少API Keys！\033[0m")
        print("请确保您已在项目根目录创建了 .env 文件，并包含所有必需的API Keys。\n")
    else:
        app.run(debug=True, threaded=True)