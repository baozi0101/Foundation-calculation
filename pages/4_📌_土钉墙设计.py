import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.inputs import render_soil_editor
from core.soil_mechanics import calculate_earth_pressure
from core.structures.soil_nail_wall import SoilNailWall
from utils.materials import CONCRETE_PROPERTIES, STEEL_PROPERTIES
from utils.config import init_global_state

st.set_page_config(page_title="土钉墙综合设计", layout="wide")
init_global_state()

st.title("📌 土钉墙设计与整体稳定验算")

# ================= 1. 侧边栏 =================
with st.sidebar:
    st.header("⚙️ 基坑参数")
    st.session_state.safety_level = st.selectbox("基坑安全等级", options=["一级", "二级", "三级"], index=["一级", "二级", "三级"].index(st.session_state.safety_level))
    st.session_state.H0 = st.number_input("基坑深度 h (m)", value=st.session_state.H0, step=0.5)
    # <--- 【修改点】：修改及新增水位UI参数
    st.session_state.zw_out = st.number_input("坑外水位 zw_out (m)", value=st.session_state.zw_out, step=0.5)
    st.session_state.zw_in = st.number_input("坑内水位 zw_in (m)", value=st.session_state.zw_in, step=0.5, min_value=0.0)
    st.session_state.q = st.number_input("地表超载 q (kPa)", value=st.session_state.q, step=5.0)

    H0 = st.session_state.H0
    zw_out = st.session_state.zw_out # <--- 【修改点】
    zw_in = st.session_state.zw_in   # <--- 【修改点】
    q = st.session_state.q
    safety_level = st.session_state.safety_level

# 严格遵循规范系数映射
level_map = {
    '一级': {'Kt': 1.80, 'Ks': 1.35},
    '二级': {'Kt': 1.60, 'Ks': 1.30},
    '三级': {'Kt': 1.40, 'Ks': 1.25},
}
factors = level_map[safety_level]

df_soil = render_soil_editor()

st.subheader("📏 土钉参数与面层材料")
col1, col2, col3, col4 = st.columns(4)
nail_Sx = col1.number_input("土钉水平间距 Sx (m)", value=1.50, step=0.10)
nail_Sz = col2.number_input("土钉竖向间距 Sz (m)", value=1.50, step=0.10)
nail_alpha = col3.number_input("土钉倾角 α (°)", value=15.0, step=1.0)
nail_d = col4.number_input("成孔直径 d (mm)", value=100.0, step=10.0) / 1000.0

col5, col6, col7 = st.columns(3)
conc_grade = col5.selectbox("面层喷射混凝土等级", options=["C20", "C25", "C30"], index=0)
steel_grade = col6.selectbox("土钉钢筋等级", options=list(STEEL_PROPERTIES.keys()), index=1)
face_t = col7.number_input("面层厚度 (mm)", value=100.0, step=10.0) / 1000.0

# 默认生成均匀分布的土钉
num_nails = int(H0 // nail_Sz)
default_depths = [nail_Sz * (i + 1) for i in range(num_nails)]
default_lengths = [H0 * 1.2 for _ in range(num_nails)]

st.markdown("**📌 土钉布置方案 (深度与长度)**")
cols = st.columns(min(num_nails, 6))
nail_depths = []
nail_lengths = []
for i in range(num_nails):
    with cols[i % 6]:
        z_i = st.number_input(f"第 {i+1} 层深度", value=default_depths[i], step=0.1, key=f"z_{i}")
        L_i = st.number_input(f"第 {i+1} 层长度", value=default_lengths[i], step=0.5, key=f"l_{i}")
        nail_depths.append(z_i)
        nail_lengths.append(L_i)

def draw_nail_profile(fig, layer_stats, L, nail_df, x_max=12):
    colors = ['#f4f1de', '#e07a5f', '#3d405b', '#81b29a', '#f2cc8f', '#e5989b', '#98c1d9']
    for i, stat in enumerate(layer_stats):
        c_color = colors[i % len(colors)]
        fig.add_shape(type="rect", x0=0, x1=x_max, y0=stat['top'], y1=stat['bot'], fillcolor=c_color, opacity=0.4, layer="below", line_width=1)
        if stat['bot'] > H0:
            fig.add_shape(type="rect", x0=-x_max, x1=0, y0=max(stat['top'], H0), y1=stat['bot'], fillcolor=c_color, opacity=0.4, layer="below", line_width=1)

    fig.add_shape(type="line", x0=0, x1=0, y0=0, y1=H0, line=dict(color="black", width=4)) # 坡面
    fig.add_hline(y=H0, line_dash="dash", line_color="green", annotation_text="基坑底", annotation_position="bottom left")

    # 绘制土钉
    alpha_rad = np.radians(nail_alpha)
    for _, row in nail_df.iterrows():
        z_start = row['深度 z (m)']
        l_nail = row['长度 L (m)']
        x_end = l_nail * np.cos(alpha_rad)
        z_end = z_start + l_nail * np.sin(alpha_rad)
        fig.add_trace(go.Scatter(x=[0, x_end], y=[z_start, z_end], mode='lines+markers', line=dict(color='red', width=3), marker=dict(symbol='circle', size=6, color='black'), name=f"土钉 {row['层号']}"))

# ================= 2. 核心计算 =================
if not df_soil.empty:
    # <--- 【修改点】：传入 zw_out 和 zw_in
    calc_df, layer_stats = calculate_earth_pressure(df_soil, H0, zw_out, zw_in, q)
    fc_val = 9.6 if conc_grade == "C20" else 11.9
    fy_val = STEEL_PROPERTIES[steel_grade]['f_y']
    
    wall = SoilNailWall(Sx=nail_Sx, Sz=nail_Sz, alpha=nail_alpha, d_hole=nail_d, fyk=fy_val, f_c=fc_val, fc_grade=conc_grade)
    
    nail_res_df, phi_m = wall.calc_nail_forces(calc_df, H0, nail_depths, nail_lengths, layer_stats, df_soil)
    face_res = wall.calc_facing_design(nail_res_df['拉力 Nk (kN)'].max(), thickness=face_t)
    gs_res = wall.calc_global_stability(H0, q, layer_stats, nail_res_df)
    
    st.markdown("---")
    col_chart, col_process = st.columns([1.1, 1.2])
    
    with col_process:
        st.subheader("📝 详细设计与验算书")
        
        with st.expander("步骤一：土钉轴向拉力与抗拔验算 (包含单根详情)", expanded=True):
            st.markdown("依据《建筑基坑支护技术规程》7.1 节公式：")
            st.latex(f"N_{{k,j}} = \\frac{{1}}{{\\cos\\alpha_j}} \\zeta \\eta_j p_{{akj}} s_x s_z")
            st.latex(f"R_{{k,j}} = \\pi d_j \\sum q_{{sik}} l_i")
            st.markdown(f"**安全等级 {safety_level}，抗拔安全系数要求**：$K_t \\ge {factors['Kt']}$")
            
            st.markdown("**【每根土钉详细计算过程】**")
            for i, row in nail_res_df.iterrows():
                j = int(row['层号'])
                st.markdown(f"**👉 第 {j} 层土钉 (深度 {row['深度 z (m)']} m)**：")
                st.latex(f"N_{{k,{j}}} = \\frac{{1}}{{\\cos({nail_alpha}^\\circ)}} \\times 1.0 \\times 1.0 \\times {row['ea (kPa)']} \\times {nail_Sx} \\times {nail_Sz} = {row['拉力 Nk (kN)']} \\text{{ kN}}")
                
                if row['有效长 Lout (m)'] <= 0:
                    st.latex(f"R_{{k,{j}}} = 0 \\text{{ kN (未能穿透破裂面)}}")
                else:
                    st.latex(f"R_{{k,{j}}} = \\pi \\times {nail_d} \\times ({row.get('分段详情', '0')}) = {row['抗拔 Rk (kN)']} \\text{{ kN}}")
                    
                st.latex(f"K_t = \\frac{{{row['抗拔 Rk (kN)']}}}{{{row['拉力 Nk (kN)']}}} = {row['Kt']}")
            
            st.divider()
            st.markdown("**【全抗拔力验算汇总表】**")
            format_dict = {"ea (kPa)": "{:.2f}", "拉力 Nk (kN)": "{:.2f}", "有效长 Lout (m)": "{:.2f}", "抗拔 Rk (kN)": "{:.2f}", "Kt": "{:.2f}"}
            st.dataframe(nail_res_df.style.format(format_dict), use_container_width=True)
            
            min_Kt = nail_res_df['Kt'].min()
            if min_Kt >= factors['Kt']:
                st.success(f"所有土钉抗拔承载力均满足要求 (最小 Kt = {min_Kt:.2f} ≥ {factors['Kt']}) ✅")
            else:
                st.error(f"部分土钉抗拔承载力不足 (最小 Kt = {min_Kt:.2f} < {factors['Kt']}) ❌")

        with st.expander("步骤二：面层承载力与配筋计算 (简支单向板)", expanded=True):
            st.markdown("面层计算单元取单根土钉影响范围，按简支单向板计算跨中弯矩：")
            st.latex(f"p = 1.25 \\times \\frac{{N_{{k,max}}}}{{s_x s_z}} = 1.25 \\times \\frac{{{nail_res_df['拉力 Nk (kN)'].max():.1f}}}{{{nail_Sx} \\times {nail_Sz}}} = {face_res['p']:.1f} \\text{{ kPa}}")
            st.latex(f"M = \\frac{{1}}{{8}} p L_0^2 = \\frac{{1}}{{8}} \\times {face_res['p']:.1f} \\times {min(nail_Sx, nail_Sz)}^2 = {face_res['M']:.2f} \\text{{ kN}}\\cdot\\text{{m/m}}")
            
            st.markdown("单筋矩形截面受弯配筋：")
            st.latex(f"\\alpha_s = \\frac{{M}}{{\\alpha_1 f_c b h_0^2}} = {face_res['alpha_s']:.3f}")
            st.latex(f"A_s = {face_res['As']:.0f} \\text{{ mm}}^2\\text{{/m}} \\quad (A_{{s,min}} = {face_res['As_min']:.0f} \\text{{ mm}}^2\\text{{/m}})")
            st.success(f"👉 **面层配筋建议**：配置钢筋网片面积 $\ge {face_res['As']:.0f}$ mm²/m")

        with st.expander("步骤三：整体稳定性验算 (带土钉抗力的条分法)", expanded=True):
            st.markdown("依据《建筑基坑支护技术规程》JGJ 120 附录 4.2.3，采用网格寻优，将土钉提供的极限抗拔力投影后加入圆弧滑动抗滑力矩中：")
            st.latex(r"K_s = \frac{\sum [c_j l_j + W_j\cos\theta_j\tan\varphi_j] + \sum R_{k,k}[\cos(\theta_k+\alpha_k) + \psi_v]/s_{x,k}}{\sum W_j\sin\theta_j}")
            
            st.markdown(f"**1. 圆心搜索结果**：$X_c = {gs_res['xc']:.1f}$ m, $Z_c = {gs_res['zc']:.1f}$ m, 半径 $R = {gs_res['R']:.1f}$ m。")
            st.markdown(f"**2. 滑体垂直条分与纯土体力学计算表 (切分带宽 $b_j={gs_res['b_slice']:.2f}$ m)**：")
            
            df_slices = pd.DataFrame(gs_res['slices_data'])
            if not df_slices.empty:
                st.dataframe(df_slices.style.format({"x_mid (m)": "{:.2f}", "厚度 h (m)": "{:.2f}", "倾角 θ (°)": "{:.2f}", "弧长 l (m)": "{:.2f}", "自重+超载 (kN/m)": "{:.2f}", "抗滑力 (kN/m)": "{:.2f}", "下滑力 (kN/m)": "{:.2f}"}), height=250)
                
                mid_idx = len(df_slices) // 2
                mid_row = df_slices.iloc[mid_idx]
                st.markdown(f"**3. 土体条带计算算例 (以第 {mid_idx+1} 号条带为例)**：")
                st.markdown(f"该条带所在位置 $X = {mid_row['x_mid (m)']}$ m，深度 $Z = {(gs_res['zc'] + np.sqrt(gs_res['R']**2 - (mid_row['x_mid (m)'] - gs_res['xc'])**2)) / 2:.2f}$ m。")
                st.latex(f"W_j = \\Delta G_j + q_j b_j = {mid_row['自重+超载 (kN/m)']:.1f} \\text{{ kN/m}}")
                st.latex(f"R_j = c_j l_j + W_j \\cos\\theta_j \\tan\\varphi_j = {mid_row['抗滑力 (kN/m)']:.1f} \\text{{ kN/m}}")
                st.latex(f"T_j = W_j \\sin\\theta_j = {mid_row['下滑力 (kN/m)']:.1f} \\text{{ kN/m}}")
            
            st.markdown(f"**4. 整体稳定性结论** (安全等级: {safety_level}, 限值: $K_s \\ge {factors['Ks']}$)")
            st.latex(f"M_{{resist}} = {gs_res['M_resist_soil']:.1f} \\text{{ (纯土体)}} + {gs_res['M_resist_nail']:.1f} \\text{{ (土钉抗拉)}} = {gs_res['M_resist_soil'] + gs_res['M_resist_nail']:.1f} \\text{{ kN}}\\cdot\\text{{m/m}}")
            st.latex(f"M_{{drive}} = {gs_res['M_drive']:.1f} \\text{{ kN}}\\cdot\\text{{m/m}}")
            st.latex(f"K_s = \\frac{{{gs_res['M_resist_soil'] + gs_res['M_resist_nail']:.1f}}}{{{gs_res['M_drive']:.1f}}} = {gs_res['Ks']:.3f}")
            
            if gs_res['Ks'] >= factors['Ks']:
                st.success(f"整体稳定性满足要求 (Ks ≥ {factors['Ks']}) ✅")
            else:
                st.error(f"整体稳定性不足 ❌")

    # ---------------- 左侧：联动绘图 ----------------
    with col_chart:
        st.subheader("📊 复合土体滑移与土钉布置图")
        fig = go.Figure()
        
        x_max_plot = max(10, nail_lengths[0] + 2)
        draw_nail_profile(fig, layer_stats, H0, nail_res_df, x_max=x_max_plot)
        
        # 绘制滑裂圆弧 (条分法)
        fig.add_trace(go.Scatter(x=[gs_res['xc']], y=[gs_res['zc']], mode='markers+text', marker=dict(size=8, color='black'), text=["圆心 O"], textposition="top right", name='滑裂圆心'))
        
        for slice_info in gs_res['slices_data']:
            x_m = slice_info['x_mid (m)']
            b_j = gs_res['b_slice']
            z_surf = 0 if x_m > 0 else H0
            z_arc = gs_res['zc'] + np.sqrt(gs_res['R']**2 - (x_m - gs_res['xc'])**2)
            fig.add_shape(type="line", x0=x_m - b_j/2, x1=x_m - b_j/2, y0=z_surf, y1=z_arc, line=dict(color="black", width=1, dash="dot"))

        plot_z = gs_res['z_plot']
        plot_x = gs_res['x_plot']
        z_surf_arr = np.where(plot_x > 0, 0, H0)
        mask_underground = plot_z >= z_surf_arr
        if len(plot_x[mask_underground]) > 0:
            fig.add_trace(go.Scatter(x=plot_x[mask_underground], y=plot_z[mask_underground], mode='lines', name='最危险滑裂面', line=dict(color='blue', width=4), hovertemplate="X: %{x:.1f} m<br>Z: %{y:.1f} m<extra></extra>"))
        
        # 绘制破裂面 45+phi/2
        theta_crack = np.radians(45 + phi_m / 2)
        x_crack_top = H0 / np.tan(theta_crack)
        fig.add_trace(go.Scatter(x=[0, x_crack_top], y=[H0, 0], mode='lines', line=dict(color='gray', width=2, dash='dot'), name='朗肯理论破裂面'))

        fig.update_layout(height=500, showlegend=True, legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99), margin=dict(l=10, r=10, t=10, b=10), xaxis_title="距坡面距离 X (m)", yaxis_title="深度 (m)")
        fig.update_xaxes(range=[-5, x_max_plot])
        fig.update_yaxes(autorange="reversed", range=[H0 + 5, gs_res['zc'] - 2])
        st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        st.markdown("**图 2：面层计算简图 (立面图)**")
        fig2 = go.Figure()
        
        # 绘制面层立面网格分布
        xs = np.arange(-3*nail_Sx, 4*nail_Sx, nail_Sx)
        zs = np.arange(0, H0 + nail_Sz, nail_Sz)
        
        for x in xs:
            for z in zs:
                if z > 0 and z < H0: # 仅显示在有效范围内的钉
                    fig2.add_trace(go.Scatter(x=[x], y=[z], mode='markers', marker=dict(color='black', size=10, symbol='x'), showlegend=False))
                    
        # 绘制中心区域的面层计算单元
        center_z = zs[len(zs)//2]
        fig2.add_shape(type="rect", x0=-nail_Sx/2, x1=nail_Sx/2, y0=center_z-nail_Sz/2, y1=center_z+nail_Sz/2, line=dict(color="blue", dash="dash", width=3), fillcolor="rgba(0,0,255,0.1)")
        fig2.add_annotation(x=0, y=center_z, text="计算单元 ($S_x \\times S_z$)", showarrow=True, arrowhead=2, ax=60, ay=-40, font=dict(color="blue", size=14))
        
        fig2.update_layout(height=400, xaxis_title="面层水平跨度 X (m)", yaxis_title="深度 Z (m)", margin=dict(l=10, r=10, t=10, b=10))
        fig2.update_yaxes(autorange="reversed", range=[H0, 0])
        st.plotly_chart(fig2, use_container_width=True)
