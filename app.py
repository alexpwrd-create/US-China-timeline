import json
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
HISTORY_START = date(2016, 11, 8)

CATEGORIES = [
    "高层外交",
    "外交对话",
    "经贸与关税",
    "制裁与反制",
    "科技与出口管制",
    "台湾与安全",
    "多边外交",
    "禁毒与执法",
    "气候与人文交流",
    "其他",
]

SCOPE_LABELS = {
    "us_china": "🔵 中美 / U.S.–China",
    "international": "🟣 国际 / International",
    "other_country": "🟠 其他国家和地区 / Other countries and regions",
}

st.set_page_config(
    page_title="中美外交大事记与未来议程",
    page_icon="🌐",
    layout="wide",
)

def read_json(filename):
    path = DATA_DIR / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, list):
            return value
        st.error(f"{filename} 的最外层必须是 JSON 数组，例如 []。")
        return []
    except FileNotFoundError:
        st.warning(f"找不到文件：{filename}")
        return []
    except json.JSONDecodeError as exc:
        st.error(f"{filename} 不是有效 JSON：{exc}")
        return []

def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None

def get_categories(event):
    value = event.get("category", [])
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    return []

def flatten_text(value):
    if isinstance(value, dict):
        return " ".join(flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(v) for v in value)
    if isinstance(value, str):
        return value
    return ""

def get_sources(item):
    sources = item.get("sources", [])
    if not isinstance(sources, list):
        sources = []

    # 兼容旧格式的单条 source_url
    if not sources and item.get("source_url"):
        sources = [{
            "name_zh": item.get("source_name", "来源"),
            "name_en": item.get("source_name", "Source"),
            "url": item.get("source_url"),
        }]
    return sources

def render_sources(item):
    sources = get_sources(item)
    event_id = str(
    item.get("id")
    or f"{item.get('date', 'unknown')}_{item.get('title_zh', 'event')}"
)

    if not 1 <= len(sources) <= 3:
        st.warning("来源应为 1–3 条；请审核后补充或调整。")

    if sources:
        st.markdown("**信源 / Sources**")
        for index, source in enumerate(sources[:3], start=1):
            url = source.get("url", "")
            name_zh = source.get("name_zh") or source.get("name") or f"来源 {index}"
            name_en = source.get("name_en") or source.get("name") or f"Source {index}"
            if url.startswith(("https://", "http://")):
                st.link_button(
                    f"{index}. {name_zh} / {name_en}",
                    url,
                    key=f"source_{event_id}_{index}",
                )
            else:
                st.write(f"{index}. {name_zh} / {name_en}（链接待补）")

def render_bilingual_field(item, key, label_zh, label_en):
    zh = item.get(f"{key}_zh", "")
    en = item.get(f"{key}_en", "")
    if zh or en:
        st.markdown(f"**{label_zh} / {label_en}**")
        if zh:
            st.write(zh)
        if en:
            st.caption(en)

def history_page(events):
    st.title("中美外交大事记")
    st.caption(
        "U.S.–China Diplomatic Relations Timeline · "
        "自 2016 年 11 月 8 日起 · 中英对照"
    )

    events = [
    event for event in events
    if event.get("approved") is True
    and (parse_date(event.get("date")) or date.min) >= HISTORY_START
    ]

    with st.sidebar:
        st.header("大事记筛选 / Timeline filters")
        query = st.text_input("关键词 / Keyword")
        available_categories = sorted({
            category
            for event in events
            for category in get_categories(event)
        })
        selected_categories = st.multiselect(
            "领域 / Fields",
            available_categories or CATEGORIES,
        )
        years = sorted({
            str(event.get("date", ""))[:4]
            for event in events
            if event.get("date")
        }, reverse=True)
        selected_year = st.selectbox("年份 / Year", ["全部 / All"] + years)
        sort_order = st.radio(
            "排序 / Order",
            ["倒序：最新优先 / Newest first", "正序：最早优先 / Oldest first"],
        )

    filtered = []
    for event in events:
        event_categories = get_categories(event)
        search_text = flatten_text(event).lower()

        if query and query.lower() not in search_text:
            continue
        if selected_categories and not set(selected_categories).intersection(event_categories):
            continue
        if selected_year != "全部 / All" and not str(event.get("date", "")).startswith(selected_year):
            continue
        filtered.append(event)

    newest_first = sort_order.startswith("倒序")
    filtered.sort(
        key=lambda event: parse_date(event.get("date")) or date.min,
        reverse=newest_first,
    )

    st.caption(f"显示 {len(filtered)} 条 / {len(events)} 条正式事件")

    if not filtered:
        st.info(
            "目前还没有符合条件的正式事件。请将经核实的事件整理后加入 "
            "data/events.json。"
        )
        return

    for index, event in enumerate(filtered):
        event_date = event.get("date", "日期待补")
        title_zh = event.get("title_zh", "中文标题待补")
        title_en = event.get("title_en", "English title pending")
        categories = " · ".join(get_categories(event)) or "未分类 / Unclassified"

        with st.container(border=True):
            st.markdown(f"### {title_zh}（{event_date}）")
            st.markdown(f"### {title_en}")
            st.caption(f"领域 / Fields：{categories}")

            render_bilingual_field(event, "summary", "摘要", "Summary")
            render_bilingual_field(event, "participants", "参与官员与会面", "Officials and meetings")
            render_bilingual_field(event, "topics", "讨论议题", "Topics discussed")
            render_bilingual_field(event, "measures", "具体措施", "Specific measures")
            render_bilingual_field(event, "background", "背景", "Background")
            render_bilingual_field(event, "follow_up", "后续与影响", "Follow-up and impact")

            render_sources(event)

def agenda_page(agenda):
    st.title("未来 12 个月重大议程")
    st.caption("Major Events in the Next 12 Months · 中英对照")

    today = date.today()
    try:
        end_date = today.replace(year=today.year + 1)
    except ValueError:
        # 处理闰年 2 月 29 日
        end_date = today.replace(year=today.year + 1, day=28)

    st.caption(
        f"当前显示范围 / Current window: "
        f"{today.isoformat()} — {end_date.isoformat()}"
    )

    with st.sidebar:
        st.header("议程筛选 / Agenda filters")
        query = st.text_input("议程关键词 / Keyword", key="agenda_query")
        scopes = st.multiselect(
            "地区范围 / Scope",
            list(SCOPE_LABELS.keys()),
            format_func=lambda value: SCOPE_LABELS[value],
        )
        sort_order = st.radio(
            "议程排序 / Order",
            ["正序：最近优先 / Soonest first", "倒序：最远优先 / Latest first"],
            key="agenda_sort",
        )

    confirmed = []
    to_confirm = []

    for item in agenda:
        status = item.get("status", "")
        exact_date = parse_date(item.get("date"))

        searchable = flatten_text(item).lower()
        if query and query.lower() not in searchable:
            continue

        scope = item.get("scope", "")
        if scopes and scope not in scopes:
            continue

        if status == "confirmed" and exact_date and today <= exact_date <= end_date:
            confirmed.append(item)

        elif status == "to_be_confirmed":
            # 日期未定的议程须填写预计时间范围，且与未来 12 个月有重叠。
            expected_start = parse_date(item.get("expected_start"))
            expected_end = parse_date(item.get("expected_end"))

            if expected_start and expected_end:
                overlaps = expected_start <= end_date and expected_end >= today
                if overlaps:
                    to_confirm.append(item)

    soonest_first = sort_order.startswith("正序")

    def agenda_sort_key(item):
        return (
            parse_date(item.get("date"))
            or parse_date(item.get("expected_start"))
            or parse_date(item.get("expected_end"))
            or date.max
        )

    confirmed.sort(key=agenda_sort_key, reverse=not soonest_first)
    to_confirm.sort(key=agenda_sort_key, reverse=not soonest_first)

    st.subheader(f"已确认 / Confirmed（{len(confirmed)}）")
    if not confirmed:
        st.info("未来 12 个月暂无符合筛选条件的已确认议程。")

    for index, item in enumerate(confirmed):
        render_agenda_card(item, "已确认 / Confirmed", index)

    st.subheader(f"待确认 / To be confirmed（{len(to_confirm)}）")
    if not to_confirm:
        st.info("未来 12 个月暂无符合筛选条件的待确认议程。")

    for index, item in enumerate(to_confirm):
        render_agenda_card(item, "待确认 / To be confirmed", index + 10000)

def render_agenda_card(item, status_label, index):
    scope = item.get("scope", "")
    scope_label = SCOPE_LABELS.get(scope, "⚪ 未分类 / Unclassified")
    exact_date = item.get("date") or "日期待定 / Date TBC"
    title_zh = item.get("title_zh", "中文标题待补")
    title_en = item.get("title_en", "English title pending")

    with st.container(border=True):
        st.caption(f"{scope_label}　|　{status_label}")
        st.markdown(f"### {title_zh}（{exact_date}）")
        st.markdown(f"### {title_en}")

        if not item.get("date"):
            period_zh = item.get("expected_period_zh", "")
            period_en = item.get("expected_period_en", "")
            if period_zh:
                st.write(f"预计时间：{period_zh}")
            if period_en:
                st.caption(f"Expected period: {period_en}")

        render_bilingual_field(item, "summary", "内容", "Details")

        verified = item.get("last_verified", "待补")
        st.caption(f"最后核实 / Last verified: {verified}")
        render_sources(item)

events_data = read_json("history.json")
agenda_data = read_json("agenda.json")

with st.sidebar:
    page = st.radio(
        "页面 / Page",
        ["中美大事记 / Timeline", "未来 12 个月议程 / Future agenda"],
    )

if page.startswith("中美"):
    history_page(events_data)
else:
    agenda_page(agenda_data)

st.divider()
st.caption(
    "仅展示经人工审核的正式记录。自动采集线索不在此页面公开发布。"
    " / Only manually reviewed records are displayed; automated leads are not published here."
)
