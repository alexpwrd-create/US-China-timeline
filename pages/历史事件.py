import json
from datetime import date
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="中美历史事件",
    page_icon="📜",
    layout="wide",
)

# 页面文件在 pages/ 中，所以要回到仓库根目录再找到 data/history.json
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "history.json"

@st.cache_data(ttl=60)
def load_events():
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

st.title("中美历史事件")
st.caption("按事件实际发生时间排列，不显示新闻报道或抓取时间。")

try:
    events = load_events()
except FileNotFoundError:
    st.error("找不到 data/history.json，请确认文件已经提交到 GitHub。")
    st.stop()
except json.JSONDecodeError as e:
    st.error(f"history.json 格式错误：{e}")
    st.stop()

# 历史文件中只展示已确认记录
events = [
    event for event in events
    if event.get("approved") is True
]

categories = sorted({
    category
    for event in events
    for category in event.get("categories", [])
})

with st.sidebar:
    st.header("筛选")

    selected_categories = st.multiselect(
        "领域分类",
        options=categories,
        help="不选择分类时显示全部事件",
    )

    keyword = st.text_input("关键词搜索")

    sort_order = st.radio(
        "浏览顺序",
        ["由早到晚", "由晚到早"],
    )

filtered_events = []

for event in events:
    if selected_categories and not any(
        category in event.get("categories", [])
        for category in selected_categories
    ):
        continue

    searchable_text = " ".join([
        event.get("title_zh", ""),
        event.get("title_en", ""),
        event.get("description_zh", ""),
        event.get("description_en", ""),
        " ".join(event.get("categories", [])),
    ]).casefold()

    if keyword and keyword.casefold() not in searchable_text:
        continue

    filtered_events.append(event)

filtered_events.sort(
    key=lambda event: date.fromisoformat(event["date"]),
    reverse=(sort_order == "由晚到早"),
)

st.write(f"共找到 **{len(filtered_events)}** 条事件")

if not filtered_events:
    st.info("目前没有符合条件的历史事件。")

for event in filtered_events:
    with st.container(border=True):
        st.markdown(f"### {event['title_zh']}")
        st.markdown(f"### {event['title_en']}")
        st.caption(f"事件实际发生时间：{event['date']}")

        categories_text = "、".join(event.get("categories", []))
        st.markdown(f"**领域分类：** {categories_text}")

        st.markdown(event["description_zh"])
        st.markdown(event["description_en"])

        source_url = event.get("source_url", "")
        source_title = event.get("source_title", "官方信源")

        if source_url:
            st.markdown(f"**官方信源：** [{source_title}]({source_url})")
        else:
            st.warning("该事件尚未补齐官方信源链接。")
