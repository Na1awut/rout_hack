"""Ready-Mix AI dispatch -- decision support dashboard (Phase 11 / Loop 10).

    streamlit run readymix/dashboard/app.py

Replays one SIMULATED Phase 9 evaluation day under the static plan (BEFORE)
and the AI dispatcher (AFTER). Every number is computed from the run or read
from the Phase 9/10 result files; nothing is typed in by hand.
"""
import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from readymix.dashboard.trace import (PHASE9, ROOT, _rows, alerts, dataset_root, decisions, hhmm,  # noqa: E402
                                      run_traced, site_status, truck_states)

BEFORE, AFTER = "A_static_planned", "C_ai_rolling_buffered"
SCENARIOS = {"S0_normal": "S0 วันปกติ", "S1_light_traffic": "S1 รถไม่ติด", "S2_peak_traffic": "S2 รถติดหนัก",
             "S3_site_delay": "S3 ไซต์ล่าช้า", "S4_multi_site_delay": "S4 หลายไซต์ล่าช้า",
             "S5_pump_failure": "S5 ปั๊มเสีย", "S6_high_demand": "S6 งานล้นรถ",
             "S7_mixed_disruption": "S7 หลายเหตุการณ์", "S8_ai_prediction_error": "S8 AI ทายผิด"}
STATE_COLOR = {"waiting for bay": "#9e9e9e", "loading": "#6d4c41", "to site": "#1e88e5", "waiting at site": "#e53935",
               "unloading": "#43a047", "returning": "#8e24aa", "washing": "#00897b", "idle at plant": "#bdbdbd"}
DAY0 = datetime(2026, 10, 1)


@st.cache_data(show_spinner="กำลังรัน optimizer ทั้งวัน…")
def load_day(scenario, seed, nonce):
    out = {}
    for policy in (BEFORE, AFTER):
        r = run_traced(scenario, seed, policy)
        r["decisions"] = decisions(r)
        out[policy] = r
    return out


@st.cache_data
def evidence():
    comp = pd.read_csv(ROOT / "phase10_carbon_business/comparisons.csv")
    gates9 = json.loads((PHASE9 / "gates.json").read_text())
    return comp, gates9


def geo(root):
    plant = _rows(root / "master/plants.csv")[0]
    sites = {s["site_id"]: (float(s["latitude"]), float(s["longitude"])) for s in _rows(root / "master/sites.csv")}
    return (float(plant["latitude"]), float(plant["longitude"])), sites


def kpi_cards(before, after):
    kb, ka, ib, ia = before["kpi"], after["kpi"], before["impact"], after["impact"]
    items = [("รถรอที่ไซต์", kb["total_waiting_min"], ka["total_waiting_min"], "นาที", True),
             ("ไซต์ว่างรอรถ", kb["site_idle_min"], ka["site_idle_min"], "นาที", True),
             ("On-time", kb["on_time_rate"] * 100, ka["on_time_rate"] * 100, "%", False),
             ("น้ำมัน", ib["fuel_l"], ia["fuel_l"], "ลิตร", True),
             ("CO₂", ib["co2_kg"], ia["co2_kg"], "kg", True),
             ("ต้นทุนที่วัดได้", ib["cost_proxy_thb"], ia["cost_proxy_thb"], "THB", True),
             ("เที่ยวที่ส่งไม่ได้", kb["unserved_trips"], ka["unserved_trips"], "เที่ยว", True)]
    for row in (items[:4], items[4:]):
        for col, (name, b, a, unit, lower_better) in zip(st.columns(4), row):
            delta_unit = "จุด" if unit == "%" else unit
            col.metric(name, f"{a:,.0f} {unit}" if unit != "%" else f"{a:.1f}%",
                       delta=f"{a - b:+,.1f} {delta_unit}", delta_color="inverse" if lower_better else "normal")
    st.caption("ตัวเลขใหญ่ = AFTER (AI) · ลูกศร = เปลี่ยนไปเท่าไรเมื่อเทียบกับแผนเดิมในวันเดียวกัน")


def map_figure(run, t):
    (plat, plon), sites = geo(run["root"])
    status = {s["site"]: s for s in site_status(run, t)}
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[plon], y=[plat], mode="markers+text", text=["PLANT"], textposition="top center",
                             marker=dict(size=18, symbol="square", color="#212121"), name="Plant"))
    sx, sy, st_txt, sc = [], [], [], []
    for sid, (la, lo) in sites.items():
        s = status.get(sid)
        sx.append(lo)
        sy.append(la)
        if s is None:
            color, label = "#bdbdbd", sid
        elif s["unloading"]:
            color, label = "#43a047", f"{sid} เทอยู่"
        elif s["actual_ready"] != "not yet" and s["loads_done"].split("/")[0] != s["loads_done"].split("/")[1]:
            color, label = "#fb8c00", f"{sid} พร้อม รอรถ"
        else:
            color, label = "#1e88e5", sid
        st_txt.append(label)
        sc.append(color)
    fig.add_trace(go.Scatter(x=sx, y=sy, mode="markers+text", text=st_txt, textposition="bottom center",
                             marker=dict(size=14, color=sc, line=dict(width=1, color="#424242")), name="Sites"))
    trips = {tr["trip_id"]: tr for tr in run["plan"].trips}
    tx, ty, tt, tc = [], [], [], []
    for truck, s in truck_states(run["log"], t).items():
        la, lo = sites[trips[s["trip_id"]]["site_id"]]
        f = 0.0
        if s["state"] in ("waiting at site", "unloading"):
            f = 1.0
        elif s["state"] == "to site":
            f = (t - s["since"]) / max(1, s["until"] - s["since"])
        elif s["state"] == "returning":
            f = 1 - (t - s["since"]) / max(1, s["until"] - s["since"])
        tx.append(plon + f * (lo - plon))
        ty.append(plat + f * (la - plat))
        tt.append(f"{truck}: {s['state']}")
        tc.append(STATE_COLOR[s["state"]])
    fig.add_trace(go.Scatter(x=tx, y=ty, mode="markers", hovertext=tt, hoverinfo="text",
                             marker=dict(size=11, symbol="triangle-up", color=tc), name="Trucks"))
    fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="longitude", yaxis_title="latitude",
                      yaxis_scaleanchor="x", legend=dict(orientation="h"))
    return fig


def gantt(run, t):
    rows = []
    phases = [("released", "load_start", "waiting for bay"), ("load_start", "depart", "loading"),
              ("depart", "arrive", "to site"), ("arrive", "unload_start", "waiting at site"),
              ("unload_start", "unload_end", "unloading"), ("unload_end", "back", "returning")]
    for tid, lg in run["log"].items():
        for a, b, name in phases:
            if a in lg and b in lg and lg[b] > lg[a]:
                rows.append(dict(truck=lg["truck"], start=DAY0 + timedelta(minutes=lg[a]),
                                 end=DAY0 + timedelta(minutes=lg[b]), state=name, trip=tid))
    df = pd.DataFrame(rows).sort_values("truck")
    fig = px.timeline(df, x_start="start", x_end="end", y="truck", color="state", hover_data=["trip"],
                      color_discrete_map=STATE_COLOR)
    fig.add_vline(x=DAY0 + timedelta(minutes=t), line_dash="dash", line_color="#212121")
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
    fig.update_yaxes(categoryorder="category descending")
    return fig


def main():
    st.set_page_config(page_title="Ready-Mix AI Dispatch", layout="wide")
    st.sidebar.title("Ready-Mix AI Dispatch")
    scenario = st.sidebar.selectbox("Scenario", list(SCENARIOS), format_func=SCENARIOS.get, index=3)
    seed = st.sidebar.selectbox("วันประเมิน (fresh day seed)", list(range(9101, 9111)))
    now = st.sidebar.slider("Current time", time(6, 0), time(20, 0), time(10, 0), step=timedelta(minutes=5))
    t = now.hour * 60 + now.minute
    if "nonce" not in st.session_state:
        st.session_state.nonce = 0
    if st.sidebar.button("Re-optimize", type="primary", width="stretch"):
        st.session_state.nonce += 1
    runs = load_day(scenario, seed, st.session_state.nonce)
    before, after = runs[BEFORE], runs[AFTER]

    st.title("BEFORE แผนเดิม → AFTER AI + Optimizer")
    st.warning("ข้อมูลการทำงานทั้งหมดเป็น SIMULATED (Phase 6 simulator) · ตัวคูณน้ำมัน/CO₂/THB มาจาก readymix/config/impact.yaml")
    ok = all(r["log_sha256"] == r["expected_sha256"] for r in runs.values())
    st.caption(("✅ ผลที่รันสดตรงกับ run ประเมินของ Phase 9 ทุก byte" if ok else "⚠ ผลที่รันสดไม่ตรงกับ Phase 9")
               + f" · {SCENARIOS[scenario]} · day {seed}")
    kpi_cards(before, after)

    tab_live, tab_time, tab_trace, tab_evidence = st.tabs(["สถานะ ณ ตอนนี้", "Timeline รถ", "ทำไม AI ตัดสินใจแบบนี้",
                                                           "หลักฐาน 10 วัน"])
    with tab_live:
        view = st.radio("ดูระบบ", ["AFTER: AI", "BEFORE: แผนเดิม"], horizontal=True)
        run = after if view.startswith("AFTER") else before
        al = alerts(after, t)
        c1, c2 = st.columns([3, 2])
        with c1:
            st.plotly_chart(map_figure(run, t), width="stretch")
        with c2:
            st.subheader(f"Alerts @ {hhmm(t)}")
            if al:
                for a in al:
                    st.error(a)
            else:
                st.success("ไม่มี alert")
            fleet = truck_states(run["log"], t)
            counts = pd.Series([s["state"] for s in fleet.values()]).value_counts()
            idle = len(run["plan"].vehicles) - len(fleet)
            st.subheader("Fleet status")
            st.dataframe(pd.concat([counts, pd.Series({"idle at plant": idle})]).rename("trucks"),
                         width="stretch")
        st.subheader("Site status: planned vs AI predicted vs actual")
        sites = pd.DataFrame(site_status(after, t)).drop(columns=["predicted_min", "planned_min"])
        st.dataframe(sites, width="stretch", hide_index=True)

    with tab_time:
        st.subheader("AFTER: AI + Optimizer")
        st.plotly_chart(gantt(after, t), width="stretch")
        st.subheader("BEFORE: แผนเดิม")
        st.plotly_chart(gantt(before, t), width="stretch")
        st.caption("แดง = รถรอที่ไซต์ · เส้นประ = current time")

    with tab_trace:
        ds = [d for d in after["decisions"] if d["timestamp"] <= hhmm(t)]
        st.subheader(f"Recommended dispatch: {len(ds)} การปล่อยรถจนถึง {hhmm(t)}")
        flat = pd.DataFrame([{k: v for k, v in d.items() if k != "reason"} | d["reason"] for d in ds])
        if not flat.empty:
            st.dataframe(flat.iloc[::-1], width="stretch", hide_index=True)
            st.json(ds[-1])
        st.caption("target_arrival = เวลาที่ AI คาดว่าไซต์พร้อม ลบ safety buffer ที่เลือกจาก dev days ใน Phase 9")

    with tab_evidence:
        comp, gates9 = evidence()
        st.markdown(f"**Phase 9 gate (C เทียบ B ไม่มี AI):** ผ่าน {sum(gates9['gates'].values())}/{len(gates9['gates'])} · "
                    f"ดีขึ้น {gates9['mean_gain_min']:.0f} นาที/วัน-scenario · "
                    f"CI95 [{gates9['ci95'][0]:.0f}, {gates9['ci95'][1]:.0f}] · {gates9['runs']} run")
        show = comp[comp.metric.isin(["co2_kg", "cost_proxy_thb", "driver_wait_h", "crew_idle_person_h", "unserved_trips"])]
        st.dataframe(show[["system", "baseline", "scope", "metric", "saving_per_day", "saving_pct", "ci95_low",
                           "ci95_high", "verdict", "saving_per_year"]].round(2), width="stretch", hide_index=True)
        st.caption("จาก phase10_carbon_business/comparisons.csv · paired bootstrap ตามวัน · ต่อปี = 300 วัน (ASSUMED)")


if __name__ == "__main__":
    main()
