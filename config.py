import os

# 基础配置
SECRET_KEY = os.urandom(24)

# 数据库配置
SQLALCHEMY_DATABASE_URI = 'sqlite:///library.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 主题色
THEME_COLOR = '#AA2B30'