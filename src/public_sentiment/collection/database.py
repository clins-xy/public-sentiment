import hashlib
import os
import re
from datetime import datetime, timezone

from ..config.database import identifier, validate_database
from ..core.constants import SOURCE_TYPES
from ..core.sources import normalize_source


FIELD_CANDIDATES = {
    "source_keyword": ["source_keyword"],
    "id": ["note_id", "aweme_id", "video_id", "bvid", "comment_id", "content_id", "id"],
    "title": ["title", "video_title", "name"],
    "content": ["desc", "content", "description", "text", "content_text"],
    "url": ["note_url", "aweme_url", "video_url", "content_url", "url"],
    "author": ["nickname", "author", "user_nickname", "user_name"],
    "published_at": ["publish_time", "create_time", "pub_time", "published_at", "time", "add_ts"],
}


def connection_options(config, timeout):
    missing = [config[key] for key in ("host_env", "user_env", "password_env") if config[key] not in os.environ]
    if missing:
        raise RuntimeError("数据库环境变量未设置：" + "、".join(missing) + "；设置后须重启 Web 服务以供协程任务使用")
    host = os.environ[config["host_env"]].strip()
    user = os.environ[config["user_env"]].strip()
    if not host or not user:
        raise RuntimeError("数据库地址和用户不能为空")
    try:
        port = int(os.environ.get(config["port_env"], "3306"))
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError as error:
        raise RuntimeError("数据库端口须为 1–65535 的整数") from error
    options = {"host": host, "port": port, "user": user, "password": os.environ[config["password_env"]],
               "database": config["name"], "charset": "utf8mb4", "connect_timeout": timeout,
               "read_timeout": timeout, "write_timeout": timeout, "autocommit": False}
    if config["ssl_ca"]:
        options.update(ssl_ca=config["ssl_ca"], ssl_verify_cert=True, ssl_verify_identity=True)
    return options


def connect(config, timeout):
    options = connection_options(config, timeout)
    try:
        import pymysql
    except ImportError as error:
        raise RuntimeError('缺少 MySQL 驱动，请执行 uv sync --extra mysql，或 python -m pip install "PyMySQL[rsa]>=1.1.1,<2"') from error
    connection = None
    try:
        connection = pymysql.connect(**options, cursorclass=pymysql.cursors.DictCursor)
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION time_zone = %s", (config["timezone"],))
            cursor.execute("START TRANSACTION READ ONLY")
        return connection
    except pymysql.MySQLError as error:
        if connection is not None:
            connection.close()
        code = error.args[0] if error.args and isinstance(error.args[0], int) else "unknown"
        raise RuntimeError(f"数据库连接失败（MySQL {code}）：请检查地址、端口、只读账号权限、TLS 和认证配置；不输出凭据") from None


def schema_rows(connection, database):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_KEY FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION", (database,)
        )
        return cursor.fetchall()


def schema_tables(rows):
    tables = {}
    for row in rows:
        tables.setdefault(row["TABLE_NAME"], []).append({"name": row["COLUMN_NAME"], "type": row["DATA_TYPE"], "key": row["COLUMN_KEY"]})
    return tables


def platform_hint(table):
    lower = table.lower()
    for prefixes, platform, source_type in (
        (("xhs",), "小红书", "forum_post"), (("douyin", "dy_"), "抖音", "video"),
        (("bilibili", "bili_"), "哔哩哔哩", "video"), (("kuaishou", "ks_"), "快手", "video"),
        (("weibo", "wb_"), "微博", "forum_post"), (("tieba",), "百度贴吧", "forum_post"),
        (("zhihu",), "知乎", "forum_post"),
    ):
        if lower.startswith(prefixes):
            return platform, "forum_post" if "comment" in lower else source_type
    return "待确认平台", "internal_data"


def suggest_mapping(table, columns):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", table):
        return None
    available = {column["name"] for column in columns}
    fields = {field: next((candidate for candidate in candidates if candidate in available), None) for field, candidates in FIELD_CANDIDATES.items()}
    if "comment" in table.lower() and "comment_id" in available:
        fields["id"] = "comment_id"
    if not fields["id"] or not (fields["title"] or fields["content"]):
        return None
    platform, source_type = platform_hint(table)
    return {"table": table, "platform": platform, "source_type": source_type, "time_unit": "auto", "fields": {key: value for key, value in fields.items() if value}}


def inspect_database(config, timeout):
    connection = connect(config, timeout)
    try:
        tables = schema_tables(schema_rows(connection, config["name"]))
        proposals = [mapping for table, columns in tables.items() if (mapping := suggest_mapping(table, columns))]
        if config["tables"]:
            validate_mappings(config, tables)
        return {"database": config["name"], "connected": True, "configured_mappings_valid": bool(config["tables"]), "tables": [{"table": table, "columns": columns} for table, columns in tables.items()],
                "suggested_tables": proposals, "notice": "仅查询元数据，未读取正文。建议映射需要人工确认主键、时间单位、平台与来源类型，不会自动写入配置。"}
    except (ValueError, RuntimeError):
        raise
    except Exception:
        raise RuntimeError("数据库表结构检查失败，请检查 information_schema 可见性和只读权限") from None
    finally:
        connection.close()


def validate_mappings(config, schema):
    for mapping in config["tables"]:
        table = mapping["table"]
        if table not in schema:
            raise ValueError(f"已配置的表不可见或不存在：{table}")
        available = {column["name"] for column in schema[table]}
        missing = set(mapping["fields"].values()) - available
        if missing:
            raise ValueError(f"表 {table} 的映射字段不存在：{', '.join(sorted(missing))}")


def parse_time(value, unit, zone):
    if value is None or value == "":
        return ""
    from datetime import timedelta

    local_zone = timezone(timedelta(hours=8 if zone == "+08:00" else 0))
    try:
        if isinstance(value, datetime):
            timestamp = value.replace(tzinfo=value.tzinfo or local_zone)
        elif unit != "datetime" and re.fullmatch(r"\d+(\.\d+)?", str(value)):
            number = float(value)
            divisor = {"s": 1, "ms": 1000, "us": 1000000}.get(unit)
            if divisor is None:
                divisor = 1000000 if number >= 1e14 else 1000 if number >= 1e11 else 1
            timestamp = datetime.fromtimestamp(number / divisor, timezone.utc)
        else:
            timestamp = datetime.fromisoformat(str(value))
            timestamp = timestamp.replace(tzinfo=timestamp.tzinfo or local_zone)
        return timestamp.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError, OverflowError, OSError):
        return ""


def text_value(value):
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def escape_like(term):
    return term.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def query_table(cursor, mapping, query, limit):
    fields = mapping["fields"]
    columns = ", ".join(f"{identifier(column)} AS {identifier(field)}" for field, column in fields.items())
    terms = [term for term in re.split(r"[\s,，;；]+", query) if term]
    search_columns = list(dict.fromkeys(fields[field] for field in ("title", "content", "source_keyword") if field in fields))
    conditions = []
    parameters = []
    for term in terms:
        for column in search_columns:
            conditions.append(f"LOWER(COALESCE({identifier(column)}, '')) LIKE LOWER(%s) ESCAPE '!' ")
            parameters.append("%" + escape_like(term) + "%")
    where = " WHERE (" + " OR ".join(conditions) + ")" if conditions else ""
    order = f"{identifier(fields['published_at'])} DESC, " if "published_at" in fields else ""
    statement = f"SELECT {columns} FROM {identifier(mapping['table'])}{where} ORDER BY {order}{identifier(fields['id'])} DESC LIMIT %s"
    cursor.execute(statement, tuple(parameters + [limit]))
    return cursor.fetchall()


def collect_database(payload):

    config = payload["config"]["database"]
    validate_database(config)
    if not config["tables"]:
        raise RuntimeError("尚未配置数据库表映射：先运行 .\\run.ps1 -InspectDatabase，再确认并保存 database.tables")
    mappings = [mapping for mapping in config["tables"] if mapping["source_type"] in payload["source_types"]]
    if not mappings:
        return {"sources": [], "warnings": ["所选来源类型没有数据库表映射；不会使用示例数据补充"], "mode": "database"}
    connection = connect(config, payload["config"]["system"]["request_timeout"])
    sources = []
    warnings = []
    limit = payload["config"]["system"]["max_results"]
    try:
        schema = schema_tables(schema_rows(connection, config["name"]))
        validate_mappings({**config, "tables": mappings}, schema)
        with connection.cursor() as cursor:
            for mapping in mappings:
                available = {column["name"] for column in schema[mapping["table"]]}
                if "source_keyword" in available and "source_keyword" not in mapping["fields"]:
                    mapping = {**mapping, "fields": {**mapping["fields"], "source_keyword": "source_keyword"}}
                rows = query_table(cursor, mapping, payload["query"], limit)
                if len(rows) == limit:
                    warnings.append(f"{mapping['table']} 达到 {limit} 条截断上限，结果不是全库统计")
                skipped = 0
                for row in rows:
                    primary_key = text_value(row.get("id"))
                    title = text_value(row.get("title")).strip()
                    content = text_value(row.get("content")).strip()
                    if not primary_key or not (title or content):
                        skipped += 1
                        continue
                    locator = {"database": config["name"], "table": mapping["table"], "primary_key_column": mapping["fields"]["id"], "primary_key": primary_key}
                    identity = hashlib.sha256((config["name"] + ":" + mapping["table"] + ":" + primary_key).encode()).hexdigest()[:32]
                    published_at = parse_time(row.get("published_at"), mapping.get("time_unit", "auto"), config["timezone"])
                    if row.get("published_at") not in (None, "") and not published_at:
                        warnings.append(f"{mapping['table']} 存在无法解析的时间，时间线对应项标为未知，请检查 time_unit")
                    source = normalize_source({"id": "db-" + identity, "title": title or content[:80], "content": content or title,
                                               "source_type": mapping["source_type"], "url": text_value(row.get("url")),
                                               "author": text_value(row.get("author")) or "未署名", "published_at": published_at, "demo": False}, len(sources))
                    source.update(origin="database", platform=mapping.get("platform", ""), locator=locator,
                                  source_keyword=text_value(row.get("source_keyword")))
                    sources.append(source)
                if skipped:
                    warnings.append(f"{mapping['table']} 跳过 {skipped} 条缺少主键或正文的记录")
    except (ValueError, RuntimeError):
        raise
    except Exception:
        raise RuntimeError("数据库只读检索失败，请检查表字段、SELECT 权限、连接超时与字符集；不会回退示例数据") from None
    finally:
        connection.close()
    if len(sources) > limit:
        warnings.append(f"多表合并后按时间截取最近 {limit} 条；不代表所有历史数据")
    sources = sorted({source["id"]: source for source in sources}.values(), key=lambda source: source["published_at"], reverse=True)[:limit]
    if payload["query"] and not sources:
        searched_tables = "、".join(mapping["table"] for mapping in mappings)
        warnings.append(f"以下表已实时查询但未命中：{searched_tables}。检索标题、正文及可用的 source_keyword 采集主题词；连续输入按完整短语匹配，可改为空格分隔的多个关键词（任意词命中）。其他平台数据需先在 database.tables 配置映射；评论仅匹配自身文字，不自动关联原帖。")
    if any(source["source_keyword"] for source in sources):
        warnings.append("检索范围包含上游 source_keyword 采集主题词；主题词命中不代表正文提及该词，也不保证内容与主题相关，请结合原文核验。评论仅匹配自身文字，不自动关联原帖。")
    return {"sources": sources, "warnings": list(dict.fromkeys(warnings)), "mode": "database"}
