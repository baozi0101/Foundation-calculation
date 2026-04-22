import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.inputs import render_soil_editor
from core.soil_mechanics import calculate_earth_pressure
from core.structures.cement_wall import CementSoilWall
from utils.config import init_global_state

st.set_page_config(page_title="水泥土墙综合设计", layout="wide")
init_global_state()

st.title("🧱 水泥土墙 (重力式支护) 设计与稳定验算")

# ================= 1. 侧边栏 =================
with st.sidebar:
    st.header("⚙️ 基坑参数")
    st.session_state.safety_level = st.selectbox("基坑安全等级", options=["一级", "二级", "三级"], index=["一级", "二级", "三级"].index(st.session_state.safety_level))
    st.session_state.H0 = st.number_input("基坑深度 h (m)", value=st.session_state.H0, step=0.5)
    st.session_state.zw = st.number_input("地下水位 zw (m)", value=st.session_state.zw, step=0.5)
    st.session_state.q = st.number_input("地表超载 q (kPa)", value=st.session_state.q, step=5.0)
    st.divider()
    st.session_state.hd = st.number_input("初始嵌固深度 hd (m)", value=st.session_state.hd, step=0.1)

    H0 = st.session_state.H0
    zw = st.session_state.zw
    q = st.session_state.q
    hd = st.session_state.hd
    safety_level = st.session_state.safety_level

# 严格遵循 JGJ 120-2012 规范的安全等级系数映射
level_map = {
    '一级': {'gamma0': 1.1, 'Ks': 1.35, 'Khe': 1.80},
    '二级': {'gamma0': 1.0, 'Ks': 1.30, 'Khe': 1.60},
    '三级': {'gamma0': 0.9, 'Ks': 1.25, 'Khe': 1.40},
}
factors = level_map[safety_level]

df_soil = render_soil_editor()

st.subheader("📏 水泥土墙几何与材料参数")
col1, col2, col3 = st.columns(3)
wall_b = col1.number_input("水泥土墙厚度 b (m)", value=3.0, step=0.10)
f_cs = col2.number_input("轴心抗压强度设计值 fcs (kPa)", value=1000.0, step=100.0)
gamma_cs = col3.number_input("水泥土平均重度 γcs (kN/m³)", value=19.0, step=0.5)

def draw_pit_profile(fig, layer_stats, L, row=None, col=None, x_max=12):
    colors = ['#f4f1de', '#e07a5f', '#3d405b', '#81b29a', '#f2cc8f', '#e5989b', '#98c1d9']
    for i, stat in enumerate(layer_stats):
        c_color = colors[i % len(colors)]
        kwargs_rt = dict(type="rect", x0=wall_b, x1=x_max, y0=stat['top'], y1=stat['bot'], fillcolor=c_color, opacity=0.4, layer="below", line_width=1)
        if row and col: fig.add_shape(**kwargs_rt, row=row, col=col)
        else: fig.add_shape(**kwargs_rt)
        
        if stat['bot'] > H0:
            kwargs_lf = dict(type="rect", x0=-x_max, x1=0, y0=max(stat['top'], H0), y1=stat['bot'], fillcolor=c_color, opacity=0.4, layer="below", line_width=1)
            if row and col: fig.add_shape(**kwargs_lf, row=row, col=col)
            else: fig.add_shape(**kwargs_lf)

    # 绘制水泥土墙主体 (矩形)
    kwargs_wall = dict(type="rect", x0=0, x1=wall_b, y0=0, y1=L, fillcolor="#aaaaaa", line=dict(color="black", width=2))
    if row and col: fig.add_shape(**kwargs_wall, row=row, col=col)
    else: fig.add_shape(**kwargs_wall)
    kwargs_bot = dict(y=H0, line_dash="dash", line_color="green")
    if row and col: fig.add_hline(**kwargs_bot, row=row, col=col)
    else: fig.add_hline(**kwargs_bot, annotation_text="基坑底", annotation_position="bottom left")

# ================= 2. 核心计算 =================
if not df_soil.empty:
    calc_df, layer_stats = calculate_earth_pressure(df_soil, H0, zw, q)
    wall = CementSoilWall(b=wall_b, f_cs=f_cs, gamma_cs=gamma_cs)
    
    stab_res = wall.calc_stability(calc_df, H0, hd, zw, layer_stats)
    stress_res = wall.calc_section_stress(calc_df, H0, hd, gamma0=factors['gamma0'])
    heave_res = wall.calc_heave_stability(H0, hd, q, layer_stats)
    gs_res = wall.calc_global_stability(H0, hd, q, layer_stats)
    
    st.markdown("---")
    col_chart, col_process = st.columns([1.1, 1.2])
    
    with col_process:
        st.subheader("📝 详细设计与验算书")
        
        with st.expander("步骤一：抗倾覆稳定性验算 (Kov)", expanded=True):
            st.markdown("依据《建筑基坑支护技术规程》公式 6.2.2-1，对墙底内侧(基坑侧)取矩：")
            st.latex(f"E_{{ak}} = {stab_res['Eak']:.1f} \\text{{ kN/m}}, \\quad a_a = {stab_res['aa']:.2f} \\text{{ m}}")
            st.latex(f"E_{{pk}} = {stab_res['Epk']:.1f} \\text{{ kN/m}}, \\quad a_p = {stab_res['ap']:.2f} \\text{{ m}}")
            st.latex(f"G = \\gamma_{{cs}} \\cdot b \\cdot (h+D) = {stab_res['G']:.1f} \\text{{ kN/m}}, \\quad a_G = {wall_b/2:.2f} \\text{{ m}}")
            st.latex(f"u_m = {stab_res['um']:.1f} \\text{{ kPa}} \\quad \\text{{(墙底水压力)}}")
            
            st.latex(r"K_{ov} = \frac{E_{pk}a_p + (G - u_m b)a_G}{E_{ak}a_a}")
            st.latex(f"= \\frac{{{stab_res['Epk']:.1f} \\times {stab_res['ap']:.2f} + ({stab_res['G']:.1f} - {stab_res['um']:.1f} \\times {wall_b}) \\times {wall_b/2:.2f}}}{{{stab_res['Eak']:.1f} \\times {stab_res['aa']:.2f}}} = {stab_res['Kov']:.3f}")
            
            if stab_res['Kov'] >= 1.30:
                st.success("抗倾覆验算通过 (Kov ≥ 1.30) ✅")
            else:
                st.error("抗倾覆验算不通过 (Kov < 1.30) ❌")

        with st.expander("步骤二：抗滑移稳定性验算 (Ksl)", expanded=True):
            st.markdown("依据《建筑基坑支护技术规程》公式 6.3-1，计算墙底面的水平抗滑移能力：")
            st.latex(f"c = {stab_res['c']} \\text{{ kPa}}, \\quad \\varphi = {stab_res['phi']}^\\circ \\quad \\text{{(基底土层参数)}}")
            st.latex(r"K_{sl} = \frac{E_{pk} + (G - u_m b)\tan\varphi + c b}{E_{ak}}")
            st.latex(f"= \\frac{{{stab_res['Epk']:.1f} + ({stab_res['G']:.1f} - {stab_res['um']:.1f} \\times {wall_b}) \\times \\tan({stab_res['phi']}^\\circ) + {stab_res['c']} \\times {wall_b}}}{{{stab_res['Eak']:.1f}}} = {stab_res['Ksl']:.3f}")
            
            if stab_res['Ksl'] >= 1.20:
                st.success("抗滑移验算通过 (Ksl ≥ 1.20) ✅")
            else:
                st.error("抗滑移验算不通过 (Ksl < 1.20) ❌")

        with st.expander("步骤三：水泥土墙截面应力验算", expanded=True):
            st.markdown(f"**结构重要性系数** $\\gamma_0 = {factors['gamma0']}$， **综合分项系数** $\\gamma_F = 1.25$")
            
            st.markdown(f"**1. 正截面压应力验算** (最大弯矩截面位置 $Z_M = {stress_res['z_M']:.2f}$ m)")
            st.latex(f"M_i = \\gamma_0 \\gamma_F M_k = {factors['gamma0']} \\times 1.25 \\times {stress_res['Mk_max']:.1f} = {stress_res['Mi']:.1f} \\text{{ kN}}\\cdot\\text{{m/m}}")
            st.latex(r"\sigma_c = \gamma_0 \gamma_F \gamma_{cs} z_M + \frac{6 M_i}{b^2}")
            st.latex(f"= {factors['gamma0']} \\times 1.25 \\times {gamma_cs} \\times {stress_res['z_M']:.2f} + \\frac{{6 \\times {stress_res['Mi']:.1f}}}{{{wall_b}^2}} = {stress_res['sigma_c']:.1f} \\text{{ kPa}}")
            if stress_res['sigma_c'] <= f_cs:
                st.success(f"压应力验算满足要求 ($\sigma_c \le f_{{cs}} = {f_cs}$ kPa) ✅")
            else:
                st.error("压应力验算不满足要求 ❌")

            st.markdown(f"**2. 正截面拉应力验算**")
            st.latex(r"\sigma_t = \frac{6 M_i}{b^2} - \gamma_{cs} z_M")
            st.latex(f"= \\frac{{6 \\times {stress_res['Mi']:.1f}}}{{{wall_b}^2}} - {gamma_cs} \\times {stress_res['z_M']:.2f} = {stress_res['sigma_t']:.1f} \\text{{ kPa}}")
            limit_t = 0.15 * f_cs
            if stress_res['sigma_t'] <= limit_t:
                st.success(f"拉应力验算满足要求 ($\sigma_t \le 0.15f_{{cs}} = {limit_t}$ kPa) ✅")
            else:
                st.error("拉应力验算不满足要求 ❌")

            st.markdown(f"**3. 斜截面剪应力验算** (最大剪力截面位置 $Z_V = {stress_res['z_V']:.2f}$ m)")
            st.latex(f"V_i = \\gamma_0 \\gamma_F V_k = {factors['gamma0']} \\times 1.25 \\times {stress_res['Vk_max']:.1f} = {stress_res['Vi']:.1f} \\text{{ kN/m}}")
            st.latex(f"G_i = \\gamma_{{cs}} \\cdot b \\cdot z_V = {gamma_cs} \\times {wall_b} \\times {stress_res['z_V']:.2f} = {stress_res['Gi']:.1f} \\text{{ kN/m}}")
            st.latex(r"\tau = \frac{V_i - \mu G_i}{b} = \frac{" + f"{stress_res['Vi']:.1f} - {stress_res['mu']} \\times {stress_res['Gi']:.1f}" + f"}}{{{wall_b}}} = {stress_res['tau']:.1f} \\text{{ kPa}}")
            limit_v = f_cs / 6.0
            if stress_res['tau'] <= limit_v:
                st.success(f"剪应力验算满足要求 ($\\tau \le f_{{cs}}/6 = {limit_v:.1f}$ kPa) ✅")
            else:
                st.error("剪应力验算不满足要求 ❌")

        with st.expander("步骤四：坑底抗隆起验算 (Prandtl)"):
            st.markdown(f"**抗隆起安全系数** (安全等级: {safety_level}, 限值: $K_{{he}} \\ge {factors['Khe']}$)")
            st.latex(f"N_q = e^{{\\pi \\tan \\varphi}} \\tan^2(45^\\circ + \\varphi/2) = {heave_res['Nq']:.2f}")
            st.latex(f"N_c = (N_q - 1) / \\tan \\varphi = {heave_res['Nc']:.2f}")
            st.markdown("基底平面极限承载力 $p_{res}$ 与 滑动力 $p_{act}$：")
            st.latex(f"p_{{res}} = \\gamma_{{bot}} h_d N_q + c N_c = {heave_res['gamma_bot']:.1f} \\times {hd:.1f} \\times {heave_res['Nq']:.2f} + {heave_res['c']} \\times {heave_res['Nc']:.2f} = {heave_res['p_res']:.1f} \\text{{ kPa}}")
            st.latex(f"p_{{act}} = \\gamma_{{top}} (H_0 + h_d) + q = {heave_res['gamma_top_avg']:.1f} \\times {H0+hd:.1f} + {q} = {heave_res['p_act']:.1f} \\text{{ kPa}}")
            st.latex(f"K_{{he}} = \\frac{{p_{{res}}}}{{p_{{act}}}} = \\frac{{{heave_res['p_res']:.1f}}}{{{heave_res['p_act']:.1f}}} = {heave_res['Kl']:.3f}")
            
            if heave_res['Kl'] >= factors['Khe']:
                st.success(f"抗隆起稳定性满足规范 (Khe ≥ {factors['Khe']}) ✅")
            else:
                st.error(f"抗隆起不足 (Khe < {factors['Khe']}) ❌")

        with st.expander("步骤五：整体稳定性验算 (瑞典条分法)"):
            st.markdown("依据《建筑基坑支护技术规程》JGJ 120-2012 附录 4.2.3，采用网格寻优与圆弧滑动条分法验算：")
            st.latex(r"K_s = \frac{\sum \left\{ c_j l_j + [(q_j b_j + \Delta G_j)\cos\theta_j]\tan\varphi_j \right\} }{\sum (q_j b_j + \Delta G_j)\sin\theta_j}")
            st.markdown(f"**1. 圆弧最危险滑裂面自动搜索结果**：圆心 $X_c = {gs_res['xc']:.1f}$ m, $Z_c = {gs_res['zc']:.1f}$ m, 搜索半径 $R = {gs_res['R']:.1f}$ m。")
            st.markdown(f"**2. 滑体垂直条分与计算表 (切分带宽 $b_j={gs_res['b_slice']:.2f}$ m)**：")
            
            df_slices = pd.DataFrame(gs_res['slices_data'])
            if not df_slices.empty:
                st.dataframe(df_slices.style.format("{:.2f}", subset=['x_mid (m)', '厚度 h (m)', '倾角 θ (°)', '弧长 l (m)', '自重+超载 (kN/m)', '抗滑力 (kN/m)', '下滑力 (kN/m)']), height=250)
                
                mid_idx = len(df_slices) // 2
                mid_row = df_slices.iloc[mid_idx]
                st.markdown(f"**3. 验算算例展示 (以第 {mid_idx+1} 号条带为例)**：")
                st.markdown(f"该条带所在位置 $X = {mid_row['x_mid (m)']}$ m，深度 $Z = {(gs_res['zc'] + np.sqrt(gs_res['R']**2 - (mid_row['x_mid (m)'] - gs_res['xc'])**2)) / 2:.2f}$ m。")
                
                st.latex(f"W_j = \\Delta G_j + q_j b_j = {mid_row['自重+超载 (kN/m)']:.1f} \\text{{ kN/m}}")
                st.latex(f"R_j = c_j l_j + W_j \\cos\\theta_j \\tan\\varphi_j = {mid_row['c (kPa)']} \\times {mid_row['弧长 l (m)']} + {mid_row['自重+超载 (kN/m)']:.1f} \\times \\cos({mid_row['倾角 θ (°)']}^\\circ) \\times \\tan({mid_row['φ (°)']}^\\circ) = {mid_row['抗滑力 (kN/m)']:.1f} \\text{{ kN/m}}")
                st.latex(f"T_j = W_j \\sin\\theta_j = {mid_row['自重+超载 (kN/m)']:.1f} \\times \\sin({mid_row['倾角 θ (°)']}^\\circ) = {mid_row['下滑力 (kN/m)']:.1f} \\text{{ kN/m}}")
            
            st.markdown(f"**4. 整体稳定性结论** (安全等级: {safety_level}, 限值: $K_s \\ge {factors['Ks']}$)")
            st.latex(f"K_s = \\frac{{\\sum R_j}}{{\\sum T_j}} = \\frac{{{gs_res['M_resist']:.1f}}}{{{gs_res['M_drive']:.1f}}} = {gs_res['Ks']:.3f}")
            
            if gs_res['Ks'] >= factors['Ks']:
                st.success(f"整体稳定性满足要求 (Ks ≥ {factors['Ks']}) ✅")
            else:
                st.error(f"整体稳定性不足 (Ks < {factors['Ks']}) ❌")

    # ---------------- 左侧：上下图表联动 ----------------
    with col_chart:
        st.subheader("📊 综合受力与变形专题图")
        L = H0 + hd
        x_max_plot = max(10, wall_b + 5)

        st.markdown("**图 1：地层水泥土墙剖面与内力分布**")
        fig1 = make_subplots(rows=1, cols=3, shared_yaxes=True, subplot_titles=("<b>开挖剖面</b>", "<b>剪力 V (kN/m)</b>", "<b>弯矩 M (kN·m/m)</b>"), column_widths=[0.4, 0.3, 0.3], horizontal_spacing=0.03)
        draw_pit_profile(fig1, layer_stats, L, row=1, col=1, x_max=x_max_plot)
        fig1.add_trace(go.Scatter(x=stress_res['df']['V'], y=stress_res['df']['z'], mode='lines', name='剪力', line=dict(color='#ff7f0e', width=3), fill='tozerox', fillcolor='rgba(255, 127, 14, 0.2)'), row=1, col=2)
        fig1.add_vline(x=0, line_color="black", line_width=1, row=1, col=2)
        fig1.add_trace(go.Scatter(x=stress_res['df']['M'], y=stress_res['df']['z'], mode='lines', name='弯矩', line=dict(color='#2ca02c', width=3), fill='tozerox', fillcolor='rgba(44, 160, 44, 0.2)'), row=1, col=3)
        fig1.add_vline(x=0, line_color="black", line_width=1, row=1, col=3)
        fig1.update_layout(height=350, showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
        fig1.update_xaxes(range=[-5, x_max_plot], showgrid=False, zeroline=False, showticklabels=False, row=1, col=1)
        fig1.update_yaxes(autorange="reversed", title_text="深度 (m)", row=1, col=1)
        st.plotly_chart(fig1, use_container_width=True)

        st.divider()

        st.markdown("**图 2：瑞典条分法整体稳定滑裂面**")
        fig3 = go.Figure()
        draw_pit_profile(fig3, layer_stats, L, x_max=x_max_plot)
        
        # 1. 仅绘制圆心位置
        fig3.add_trace(go.Scatter(x=[gs_res['xc']], y=[gs_res['zc']], mode='markers+text', marker=dict(size=8, color='black'), text=["圆心 O"], textposition="top right", name='滑裂圆心'))
        
        # 2. 绘制实际滑移段（地表以下）及切分带
        for slice_info in gs_res['slices_data']:
            x_m = slice_info['x_mid (m)']
            b_j = gs_res['b_slice']
            z_surf = 0 if x_m > wall_b else H0
            z_arc = gs_res['zc'] + np.sqrt(gs_res['R']**2 - (x_m - gs_res['xc'])**2)
            fig3.add_shape(type="line", x0=x_m - b_j/2, x1=x_m - b_j/2, y0=z_surf, y1=z_arc, line=dict(color="black", width=1, dash="dot"))

        # 3. 绘制底部加粗滑弧
        plot_z = gs_res['z_plot']
        plot_x = gs_res['x_plot']
        z_surf_arr = np.where(plot_x > wall_b, 0, H0)
        mask_underground = plot_z >= z_surf_arr
        if len(plot_x[mask_underground]) > 0:
            fig3.add_trace(go.Scatter(x=plot_x[mask_underground], y=plot_z[mask_underground], mode='lines', name='最危险滑裂面', line=dict(color='blue', width=4), hovertemplate="X: %{x:.1f} m<br>Z: %{y:.1f} m<extra></extra>"))
        
        fig3.update_layout(height=500, showlegend=False, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="距基坑距离 X (m)", yaxis_title="深度 (m)")
        fig3.update_xaxes(range=[-5, x_max_plot])
        
        z_top_limit = min(-2, gs_res['zc'] - 2)
        fig3.update_yaxes(autorange="reversed", range=[L + 5, z_top_limit])
        st.plotly_chart(fig3, use_container_width=True)