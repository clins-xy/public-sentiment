import re

from ..core.constants import SOURCE_TYPES

FIELD_NAMES = {"id", "title", "content", "url", "author", "published_at", "source_keyword"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", value):
        raise ValueError("数据库、表和字段名只允许 1–64 位英文字母、数字及下划线，且不能以数字开头")
    return "`" + value + "`"


def validate_database(config):
    if config["driver"] != "mysql":
        raise ValueError("当前数据库适配器支持 MySQL / MariaDB，其他数据库需新增适配器")
    for key in ("host_env", "port_env", "user_env", "password_env"):
        if not isinstance(config[key], str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,79}", config[key]):
            raise ValueError(f"database.{key} 必须为环境变量名，不要将密码写进 config.json")
    identifier(config["name"])
    if config["timezone"] not in ("+00:00", "+08:00"):
        raise ValueError("database.timezone 支持 +00:00 或 +08:00，须与数据库无时区时间字段的实际时区一致")
    if not isinstance(config["ssl_ca"], str):
        raise ValueError("database.ssl_ca 必须为 CA 文件路径或空字符串")
    tables = config["tables"]
    if not isinstance(tables, list) or len(tables) > 20:
        raise ValueError("database.tables 必须为最多 20 项的映射数组")
    names = set()
    for mapping in tables:
        if not isinstance(mapping, dict) or set(mapping) - {"table", "source_type", "platform", "fields", "time_unit"}:
            raise ValueError("表映射仅支持 table、source_type、platform、fields、time_unit")
        identifier(mapping.get("table"))
        if mapping["table"] in names:
            raise ValueError("表映射不能重复")
        names.add(mapping["table"])
        if mapping.get("source_type") not in SOURCE_TYPES:
            raise ValueError("表映射 source_type 无效")
        if not isinstance(mapping.get("platform", ""), str) or len(mapping.get("platform", "")) > 100:
            raise ValueError("表映射 platform 必须为不超过 100 字符的名称")
        if mapping.get("time_unit", "auto") not in ("auto", "s", "ms", "us", "datetime"):
            raise ValueError("time_unit 支持 auto / s / ms / us / datetime")
        fields = mapping.get("fields")
        if not isinstance(fields, dict) or set(fields) - FIELD_NAMES or not fields.get("id") or not (fields.get("title") or fields.get("content")):
            raise ValueError("fields 必须映射 id，以及 title / content 中至少一项；只允许标准字段")
        for column in fields.values():
            identifier(column)
