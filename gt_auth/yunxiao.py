import requests

from rest_framework.exceptions import AuthenticationFailed, APIException

from proxy import get_proxy_session
from .models import SchoolChoice

LOGIN_URL = f"https://bnds.yunxiao.com/accountApi/userLogin"
USER_INFO_URL = f"https://bnds.yunxiao.com/accountApi/school/userInfo"
CAPTCHA_URL = "https://portal.yunxiao.com/api/v1/verify/captchaCode"
TIME_TABLE_URL = "https://bnds.yunxiao.com/appsApi/getStudentTimetable?id={}"


def get_partner(school):
    if school == SchoolChoice.QDZX:
        return "qdzx"
    elif school == SchoolChoice.JJLXX:
        return "jjlxx"
    raise APIException("学校错误")


def get_captcha_url(captcha_code):
    return f"{CAPTCHA_URL}/{captcha_code}"


def get_logged_session(username,
                       password,
                       school=SchoolChoice.QDZX,
                       captcha_code="",
                       captcha_value=""):
    session = get_proxy_session()

    try:
        result = session.post(
            LOGIN_URL,
            headers={
                "Host": f"{get_partner(school)}.yunxiao.com"
            },
            data={
                "account": username,
                "password": password,
                "captchaCode": captcha_code,
                "captchaValue": captcha_value,
                "rememb": False,
            },
            timeout=5,
        ).json()
    except requests.Timeout:
        raise AuthenticationFailed("云校登录错误：超时")

    if result["code"] in ["3", "4", "5"]:
        raise AuthenticationFailed(f"云校登录错误：{result['msg']}")
        return {
            "status": "error",
            "msg": result["msg"],
            "captcha_code": result["data"]["captchaCode"],
            "captcha_code_url": get_captcha_url(result["data"]["captchaCode"]),
        }
    elif result["code"] != "1":
        raise AuthenticationFailed(f"云校登录错误：{result['msg']}")

    return session


def login(username,
          password,
          school=SchoolChoice.QDZX,
          captcha_code="",
          captcha_value=""):
    session = get_logged_session(username, password, school, captcha_code,
                                 captcha_value)

    try:
        user_info = session.get(
            USER_INFO_URL,
            headers={
                "Host": f"{get_partner(school)}.yunxiao.com"
            },
            timeout=5,
        ).json()["userinfo"]
    except requests.Timeout:
        return {"status": "timeout", "msg": "Timeout", "data": None}
    user_data = {
        "account": user_info["account"],
        "name": user_info["userName"],
        "gender": user_info["gender"],
        "roles": user_info["roles"],
        "mobile": user_info["mobile"],
    }
    return {"status": "success", "data": user_data}
