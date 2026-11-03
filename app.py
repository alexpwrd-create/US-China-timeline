import csv
import io
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
DATA = ROOT / "data"

st.set_page_config(
    page_title="中美外交大事记",
    page_icon="🌐",
    layout="wide",
)

def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []

events = read_json(DATA / "events.json")
pending = read_json(DATA / "pending.json")

st.title("中美外交大事记")
st.caption("U.S.–China Diplomatic Relations Timeline · 人工审核发布")

with st.sidebar:
    st.header("筛选")
    query = st.text_input("关键词", placeholder="如：关税、Taiwan、半导体")
    categories = sorted({e.get("category", "未分类") for e in events})
    selected_category = st.selectbox("事件分类", ["全部"] + categories)
    years = sorted(
        {e.get("date", "")[:4] for e in events if e.get("date")},
        reverse=True,
    )
    selected_year = st.selectbox("年份", ["全部"] + years)
    st.divider()
    st.write(f"已审核事件：**{len(events)}**")
    st.write(f"待审核候选：**{len(pending)}**")
    st.caption("自动采集结果只作为待核查线索，不会自动发布为正式事件。")

filtered = []
for event in events:
    searchable = " ".join([
        event.get("title", ""),
        event.get("title_en", ""),
        event.get("summary", ""),
        event.get("summary_en", ""),
        event.get("category", ""),
    ]).lower()

    if query and query.lower() not in searchable:
        continue
    if selected_category != "全部" and event.get("category") != selected_category:
        continue
    if selected_year != "全部" and not event.get("date", "").startswith(selected_year):
        continue
    filtered.append(event)

filtered.sort(key=lambda item: item.get("date", ""), reverse=True)

tab_events, tab_review = st.tabs([
    f"已审核事件（{len(filtered)}）",
    f"待人工审核（{len(pending)}）",
])

with tab_events:
    if not filtered:
        st.info("目前没有符合筛选条件的已审核事件。")
    else:
        rows = []
        for event in filtered:
            rows.append({
                "日期": event.get("date", ""),
                "分类": event.get("category", ""),
                "中文标题": event.get("title", ""),
                "English title": event.get("title_en", ""),
                "中文摘要": event.get("summary", ""),
                "English summary": event.get("summary_en", ""),
                "来源": event.get("source_url", ""),
            })

            heading = f"{event.get('date', '日期待核')} · {event.get('title', '无标题')}"
            with st.expander(heading):
                if event.get("title_en"):
                    st.markdown(f"**{event['title_en']}**")
                st.write(event.get("summary", ""))
                if event.get("summary_en"):
                    st.caption(event["summary_en"])
                if event.get("background"):
                    st.markdown("**背景与后续**")
                    st.write(event["background"])
                st.caption(f"分类：{event.get('category', '未分类')}")
                if event.get("source_url"):
                    st.link_button(
                        f"打开来源：{event.get('source_name', '原始资料')}",
                        event["source_url"],
                    )

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        st.download_button(
            "下载当前筛选结果 CSV",
            data="\ufeff" + csv_buffer.getvalue(),
            file_name="us-china-timeline.csv",
            mime="text/csv",
        )

with tab_review:
    st.warning(
        "以下为关键词自动筛选出的候选信息，未经过事实核实；"
        "标题和摘要来自信息源或新闻索引，不代表本站立场。"
    )

    if pending:
        export_payload = json.dumps(pending, ensure_ascii=False, indent=2)
        st.download_button(
            "下载候选 JSON，供整理审核",
            data=export_payload,
            file_name="pending-candidates.json",
            mime="application/json",
        )

        for item in sorted(
            pending,
            key=lambda candidate: candidate.get("date", ""),
            reverse=True,
        ):
            heading = (
                f"{item.get('date') or '日期待核'} · "
                f"{item.get('title', '无标题')}"
            )
            with st.expander(heading):
                st.write(
                    f"分类：{item.get('category', '未分类')} · "
                    f"来源：{item.get('source_name', '未知来源')}"
                )
                if item.get("excerpt"):
                    st.write(item["excerpt"])
                st.link_button(
                    "打开原始来源",
                    item.get("source_url", "https://example.com"),
                )
                st.caption(
                    "审核后请人工补充准确日期、背景和中英文摘要，"
                    "再提交到 data/events.json。"
                )
    else:
        st.success("当前没有待审核候选。")

st.divider()
st.caption(
    "数据通过 GitHub 仓库维护。每小时自动采集不保证准点执行；"
    "GitHub Actions 可能延迟，来源 RSS 也可能变更。"
)
