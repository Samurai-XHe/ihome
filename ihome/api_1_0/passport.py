import re

from flask import request, jsonify, current_app, session
from . import api
from ihome.utils.response_code import RET
from ihome import redis_store, db, constants
from ihome.models import User
from sqlalchemy.exc import IntegrityError


@api.route('/users', methods=['POST'])
def register():
    """
    注册
    :param: 手机号，短信验证码，密码，确认密码
    :return:json
    """
    # 获取参数
    req_dict = request.get_json()
    mobile = req_dict.get('mobile')
    sms_code = req_dict.get('sms_code')
    password = req_dict.get('password')
    password2 = req_dict.get('password2')

    # 效验参数
    if not all([mobile, sms_code, password, password2]):
        return jsonify(errno=RET.PARAMERR, errmsg='参数不完整')

    # 判断手机号格式
    if not re.match(r'1[345678]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg='手机格式错误')

    # 判断两次密码是否一致
    if password != password2:
        return jsonify(errno=RET.PARAMERR, errmsg='两次密码不一致')

    # 从redis中取出短信验证码
    try:
        real_sms_code = redis_store.get('sms_code_%s' % mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='读取真实短信验证码异常')

    # 判断短息验证码是否过期
    if real_sms_code is None:
        return jsonify(errno=RET.NODATA, errmsg='短信验证码失效')

    # 删除redis中的短信验证码
    try:
        redis_store.delete('sms_code_%s' % mobile)
    except Exception as e:
        current_app.logger.error(e)

    # 判断用户填写的短信验证码是否正确
    # 从redis中取出的是bytes类型，需要解码
    real_sms_code = real_sms_code.decode()
    if real_sms_code != sms_code:
        return jsonify(errno=RET.DATAERR, errmsg='短信验证码错误')

    # 保存用户注册数据到数据库
    user = User()
    user.name = mobile
    user.mobile = mobile
    user.password = password

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError as e:
        # 数据库操作错误后的回滚
        # 手机号出现了重复，即手机号已被注册
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAEXIST, errmsg='手机号已存在')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg='查询数据库异常')

    # 保存登录状态到session
    session['name'] = mobile
    session['mobile'] = mobile
    session['user_id'] = user.id

    return jsonify(errno=RET.OK, errmsg='注册成功')


@api.route('/session', methods=['POST'])
def login():
    """
    用户登录
    :param: 手机号，密码
    :return:
    """
    # 获取参数
    req_dict = request.get_json()
    mobile = req_dict.get('mobile', '')
    password = req_dict.get('password')

    # 效验参数
    if not all([mobile, password]):
        return jsonify(errno=RET.DATAERR, errmsg='参数不完整')

    # 手机号的格式
    if not re.match(r'1[345678]\d{9}', mobile):
        return jsonify(errno=RET.DATAERR, errmsg='手机号格式不正确')

    # 判断错误次数是否超过限制，如果超过限制，则返回
    # redis记录： "access_nums_请求的ip": "次数"
    user_ip = request.remote_addr  # 用户的ip地址
    try:
        access_nums = redis_store.get('access_nums_%s' % user_ip)
    except Exception as e:
        current_app.logger.error(e)
    else:
        if access_nums is not None and int(access_nums) >= constants.LOGIN_ERROR_MAX_TIMES:
            return jsonify(errno=RET.REQERR, errmsg='错误次数太多，请稍后重试')

    # 从数据库中根据手机号查询寻用户的数据对象
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg='获取用户信息失败')

    # 用数据库的密码和用户填写的密码进行对比验证
    if user is None or not user.check_password(password):
        # 如果验证失败，记录错误次数，返回信息
        try:
            # redis的incr可以对字符串类型的数字数据进行加一操作，如果数据一开始不存在，则会初始化为1
            redis_store.incr('access_nums_%s' % user_ip)
            redis_store.expire('access_nums_%s' % user_ip, constants.LOGIN_ERROR_FORBID_TIME)
        except Exception as e:
            current_app.logger.error(e)

        return jsonify(errno=RET.DATAERR, errmsg='用户名或密码错误')

    # 如果验证通过，在session中保存登陆状态
    session['name'] = user.name
    session['mobile'] = user.mobile
    session['user_id'] = user.id

    return jsonify(errno=RET.OK, errmsg='登陆成功')


@api.route('/session', methods=['GET'])
def check_login():
    """检查登陆状态"""
    # 尝试从session中获取用户的名字
    name = session.get('name')
    # 如果session中数据name名字存在，则表示用户已登录，否则未登录
    if name:
        return jsonify(errno=RET.OK, errmsg='ture', data={'name': name})
    else:
        return jsonify(errno=RET.SESSIONERR, errmsg='false')


@api.route('/session', methods=['DELETE'])
def logout():
    """登出"""
    # 清除session数据
    session.clear()
    return jsonify(errno=RET.OK, errmsg='ok')
