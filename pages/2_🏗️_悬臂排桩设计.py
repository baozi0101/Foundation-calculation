import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.inputs import render_soil_editor
from core.soil_mechanics import calculate_earth_pressure
from core.structures.pile import RetainingPile
from utils.materials import CONCRETE_PROPERTIES, STEEL_PROPERTIES
from utils.config import init_global_state

st.set_page_config(page_title="悬臂排桩综合设计", layout="wide")
init_global_state()

st.title("🏗️ 悬臂式排桩设计与综合稳定验算")

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
    '一级': {'gamma0': 1.1, 'Kem': 1.25, 'Ks': 1.35, 'Khe': 1.80},
    '二级': {'gamma0': 1.0, 'Kem': 1.20, 'Ks': 1.30, 'Khe': 1.60},
    '三级': {'gamma0': 0.9, 'Kem': 1.15, 'Ks': 1.25, 'Khe': 1.40},
}
factors = level_map[safety_level]

df_soil = render_soil_editor()

st.subheader("📏 排桩截面与材料参数")
col1, col2, col3, col4 = st.columns(4)
pile_d = col1.number_input("桩身直径 d (m)", value=0.80, step=0.10)
pile_s = col2.number_input("桩中心间距 s (m)", value=1.60, step=0.10)
conc_grade = col3.selectbox("混凝土强度等级", options=list(CONCRETE_PROPERTIES.keys()), index=2)
steel_grade = col4.selectbox("纵筋强度等级", options=list(STEEL_PROPERTIES.keys()), index=1)

def draw_pit_profile(fig, layer_stats, L, row=None, col=None, x_max=12):
    colors = ['#f4f1de', '#e07a5f', '#3d405b', '#81b29a', '#f2cc8f', '#e5989b', '#98c1d9']
    for i, stat in enumerate(layer_stats):
        c_color = colors[i % len(colors)]
        kwargs_rt = dict(type="rect", x0=pile_d/2, x1=x_max, y0=stat['top'], y1=stat['bot'], fillcolor=c_color, opacity=0.4, layer="below", line_width=1)
        if row and col: fig.add_shape(**kwargs_rt, row=row, col=col)
        else: fig.add_shape(**kwargs_rt)
        
        if stat['bot'] > H0:
            kwargs_lf = dict(type="rect", x0=-x_max, x1=-pile_d/2, y0=max(stat['top'], H0), y1=stat['bot'], fillcolor=c_color, opacity=0.4, layer="below", line_width=1)
            if row and col: fig.add_shape(**kwargs_lf, row=row, col=col)
            else: fig.add_shape(**kwargs_lf)

    kwargs_pile = dict(type="rect", x0=-pile_d/2, x1=pile_d/2, y0=0, y1=L, fillcolor="#555555", line=dict(color="black", width=2))
    if row and col: fig.add_shape(**kwargs_pile, row=row, col=col)
    else: fig.add_shape(**kwargs_pile)
    kwargs_bot = dict(y=H0, line_dash="dash", line_color="green")
    if row and col: fig.add_hline(**kwargs_bot, row=row, col=col)
    else: fig.add_hline(**kwargs_bot, annotation_text="基坑底", annotation_position="bottom left")

# ================= 2. 核心计算 =================
if not df_soil.empty:
    calc_df, layer_stats = calculate_earth_pressure(df_soil, H0, zw, q)
    pile = RetainingPile(pile_d, pile_s, conc_grade, steel_grade)
    
    forces_df, M_max, V_max, z_zero_shear, v_str, m_str = pile.calc_internal_forces(calc_df, H0, hd)
    ov_res = pile.calc_overturning_stability(calc_df, H0, hd)
    rebar = pile.calc_reinforcement(M_max, gamma_0=factors['gamma0'])
    shear_res = pile.calc_shear_reinforcement(V_max, gamma_0=factors['gamma0'])
    cap_res = pile.calc_capping_beam()
    set_res = pile.calc_settlement(H0, hd, layer_stats)
    heave_res = pile.calc_heave_stability(H0, hd, q, layer_stats)
    gs_res = pile.calc_global_stability(H0, hd, q, layer_stats)
    
    st.markdown("---")
    col_chart, col_process = st.columns([1.1, 1.2])
    
    with col_process:
        st.subheader("📝 详细设计与验算书")
        
        with st.expander("步骤一：内力计算 (剪力与弯矩)"):
            # 提取最大剪力所在深度
            z_vmax = forces_df.loc[(forces_df['V'].abs() - V_max).abs().idxmin(), 'z']
            
            st.markdown("**1. 剪力计算及最大剪力位置**")
            st.markdown("利用合力累加法自上而下计算剪力，剪力最大值通常出现在基坑底面附近：")
            st.latex(r"\begin{aligned} V_{max} &= \sum E_{ai} \\ &= " + f"{v_str} \\\\ &= {V_max:.2f} \\text{{ kN/m}} \\end{{aligned}}")
            st.markdown(f"**最大剪力位置**：深度 $z_{{Vmax}} = {z_vmax:.2f}$ m")
            st.markdown(f"**最大剪力极值**：$V_{{max}} = {V_max:.2f}$ kN/m")
            
            st.divider()
            
            st.markdown("**2. 弯矩计算及最大弯矩位置**")
            st.markdown("根据材料力学原理，弯矩极值出现在剪力为零的截面。通过遍历剪力数组，寻找剪力由正转负的深度 $z_0$：")
            st.latex(f"z_0 = {z_zero_shear:.2f} \\text{{ m}}")
            st.markdown("在剪力零点 $z_0$ 以上对截面取矩，计算最大弯矩：")
            st.latex(r"\begin{aligned} M_{max} &= \sum \left[ E_{ai}(z_0 - z_{ai}) - E_{pi}(z_0 - z_{pi}) \right] \\ &= " + f"{m_str} \\\\ &= {M_max:.2f} \\text{{ kN}}\\cdot\\text{{m/m}} \\end{{aligned}}")
            st.markdown(f"**剪力零点（最大弯矩位置）**：$z_0 = {z_zero_shear:.2f}$ m")
            st.markdown(f"**最大弯矩极值**：$M_{{max}} = {M_max:.2f}$ kN·m/m")

        with st.expander("步骤二：嵌固深度与抗倾覆验算"):
            st.markdown(f"**1. 构造要求** $h_d \\ge 0.8h = {ov_res['min_hd']:.2f}$ m")
            if ov_res['is_hd_ok']:
                st.success(f"当前 $h_d = {hd:.2f}$ m，满足要求。")
            else:
                st.error("不满足嵌固要求！")

            st.markdown(f"**2. 嵌固稳定安全系数** (安全等级: {safety_level}, 限值: $K_{{em}} \\ge {factors['Kem']}$)")
            st.markdown("对桩底取矩，被动区抗倾覆力矩 $M_{Ep}$ 与主动区倾覆力矩 $M_{Ea}$：")
            st.latex(r"\begin{aligned} M_{Ea} &= \sum E_{ai} (L - z_{ai}) \\ &= " + f"{ov_res['ea_str']} \\\\ &= {ov_res['M_Ea']:.1f} \\text{{ kN}}\\cdot\\text{{m}} \\end{{aligned}}")
            st.latex(r"\begin{aligned} M_{Ep} &= \sum E_{pi} (L - z_{pi}) \\ &= " + f"{ov_res['ep_str']} \\\\ &= {ov_res['M_Ep']:.1f} \\text{{ kN}}\\cdot\\text{{m}} \\end{{aligned}}")
            st.latex(r"K_{em} = \frac{M_{Ep}}{M_{Ea}}" + f" = \\frac{{{ov_res['M_Ep']:.1f}}}{{{ov_res['M_Ea']:.1f}}} = {ov_res['K_s']:.3f}")
            
            if ov_res['K_s'] >= factors['Kem']:
                st.success(f"嵌固稳定验算通过 (Kem ≥ {factors['Kem']}) ✅")
            else:
                st.error(f"嵌固稳定验算不通过 (Kem < {factors['Kem']}) ❌")

        with st.expander("步骤三：排桩受弯配筋计算 (主筋)", expanded=True):
            st.markdown("依据《建筑基坑支护技术规程》JGJ 120-2012 附录 A 圆形截面受弯承载力计算：")
            st.markdown(f"**结构重要性系数** $\\gamma_0 = {factors['gamma0']}$， **综合分项系数** $\\gamma_f = 1.25$")
            st.latex(f"M_{{design}} = M_{{max}} \\times s \\times \\gamma_0 \\times \\gamma_f")
            st.latex(f"= {M_max:.2f} \\times {pile_s} \\times {factors['gamma0']} \\times 1.25 = {rebar['M_design']:.2f} \\text{{ kN}}\\cdot\\text{{m}}")
            
            st.markdown("假定轴力 $N=0$，联立求解非线性方程组：")
            st.latex(r"M \le \frac{2}{3} f_c A r \frac{\sin^3 \pi \alpha}{\pi} + f_y A_s r_s \frac{\sin \pi \alpha + \sin \pi \alpha_t}{\pi}")
            st.latex(r"\alpha f_c A \left( 1 - \frac{\sin 2\pi \alpha}{2\pi \alpha} \right) + (\alpha - \alpha_t) f_y A_s = 0")
            st.latex(r"\alpha_t = 1.25 - 2\alpha")
            
            if rebar['alpha'] > 0:
                st.markdown("通过数值迭代，求得受压区圆心角比值：")
                st.latex(f"\\alpha = {rebar['alpha']:.4f}, \\quad \\alpha_t = {rebar['alpha_t']:.4f}")
                st.latex(f"A_s = {rebar['As']:.0f} \\text{{ mm}}^2")
            else:
                st.markdown("采用近似简化公式：")
                st.latex(f"A_s = \\frac{{M_{{design}}}}{{0.85 f_y r_s \\times 2}} = \\frac{{{rebar['M_design']:.2f} \\times 10^6}}{{0.85 \\times {rebar['fy']} \\times {rebar['rs_mm']:.1f} \\times 2}} = {rebar['As']:.0f} \\text{{ mm}}^2")
                
            st.success(f"👉 **主筋实配建议**：采用对称布置，配置 **{rebar['n_bars']} 根 Φ{rebar['bar_dia']}**")

        with st.expander("步骤四：排桩受剪配筋计算 (箍筋)"):
            st.markdown("依据《混凝土结构设计规范》GB 50010 矩形截面受剪承载力公式（圆形截面作等效折算）：")
            st.latex(f"V_{{design}} = V_{{max}} \\times s \\times \\gamma_0 \\times \\gamma_f = {V_max:.2f} \\times {pile_s} \\times {factors['gamma0']} \\times 1.25 = {shear_res['V_design']:.1f} \\text{{ kN}}")
            
            st.markdown("**1. 截面抗剪上限验算 (防斜压破坏)**")
            st.latex(f"V_{{max,limit}} = 0.25 \\beta_c f_c b h_0")
            st.latex(f"= 0.25 \\times {shear_res['beta_c']:.1f} \\times {shear_res['fc']} \\times {shear_res['b']:.0f} \\times {shear_res['h0']:.0f} / 1000 = {shear_res['V_max_limit']:.1f} \\text{{ kN}}")
            if shear_res['V_design'] <= shear_res['V_max_limit']:
                st.markdown("满足 $V_{design} \\le 0.25 \\beta_c f_c b h_0$，截面尺寸符合要求。")
            else:
                st.error("截面尺寸不足（易发生斜压破坏），需加大桩径或提高混凝土强度！")
                
            st.markdown("**2. 混凝土受剪承载力计算 ($V_c$)**")
            st.latex(r"\beta_h = \left( \frac{800}{h_0} \right)^{1/4}" + f" = {shear_res['beta_h']:.3f} \\quad \\text{{(当 }} h_0 < 800 \\text{{ 时取 800)}}")
            st.latex(f"V_c = 0.7 \\beta_h f_t b h_0 = 0.7 \\times {shear_res['beta_h']:.3f} \\times {shear_res['ft']} \\times {shear_res['b']:.0f} \\times {shear_res['h0']:.0f} / 1000 = {shear_res['V_c']:.1f} \\text{{ kN}}")
            
            st.markdown("**3. 箍筋配置计算**")
            if shear_res['req_Asv_s'] == 0:
                st.success(f"因 $V_{{design}} \\le V_c$，采用构造配箍即可。")
            else:
                st.latex(f"\\frac{{A_{{sv}}}}{{s}} = \\frac{{V_{{design}} - V_c}}{{f_{{yv}} h_0}} = \\frac{{{shear_res['V_design']:.1f} - {shear_res['V_c']:.1f}}}{{{shear_res['fyv']} \\times {shear_res['h0']:.0f}}} \\times 1000 = {shear_res['req_Asv_s']:.2f} \\text{{ mm}}^2\\text{{/mm}}")
            st.info(f"👉 **箍筋实配建议**：**{shear_res['stirrup']}** (双肢箍)")

        with st.expander("步骤五：冠梁尺寸与配筋估算"):
            st.markdown("悬臂排桩顶部冠梁主要起整体连系作用，按构造要求配置：")
            st.latex(f"b = d + 100 = {pile_d*1000:.0f} + 100 = {cap_res['b']} \\text{{ mm}}")
            st.latex(f"h = \\max(400, 0.6d) = {cap_res['h']} \\text{{ mm}}")
            st.latex(f"A_{{s,min}} = 0.15\\% b h = 0.0015 \\times {cap_res['b']} \\times {cap_res['h']} = {cap_res['As_min']:.1f} \\text{{ mm}}^2")
            st.success(f"👉 **纵筋实配建议**：上下各 **{cap_res['n_bars']} 根 Φ{cap_res['bar_dia']}**")

        with st.expander("步骤六：外侧地表沉降计算 (双法对比)"):
            st.markdown("依据《理正深基坑支护结构设计软件单元计算编制原理》：")
            st.markdown(f"**1. 沉降范围 $x_0$**")
            st.latex(f"\\varphi_{{avg}} = {set_res['phi_avg']:.1f}^\\circ \\quad \\text{{(土层加权平均)}}")
            st.latex(f"x_0 = (H + D) \\tan \\left( \\frac{{\\pi}}{{4}} - \\frac{{\\varphi_{{avg}}}}{{2}} \\right) = ({H0} + {hd}) \\tan(45^\\circ - {set_res['phi_avg']/2:.1f}^\\circ) = {set_res['x0']:.2f} \\text{{ m}}")
            
            st.markdown(f"**2. 侧移面积 $S_w$ 估算**")
            st.markdown("经验假定最大侧移 $v_{max} = 0.2\\% H$，侧移呈三角形分布：")
            st.latex(f"S_w = \\frac{{1}}{{2}} v_{{max}} (H + D) = \\frac{{1}}{{2}} \\times {set_res['v_max_mm']:.1f} \\times {H0+hd} = {set_res['Sw_mm2']:.0f} \\text{{ mm}}^2")
            
            st.markdown(f"**3. 最大沉降量**")
            st.latex(f"\\delta_{{max, \\text{{三角}}}} = \\frac{{2 S_w}}{{x_0}} = \\frac{{2 \\times {set_res['Sw_mm2']:.0f}}}{{{set_res['x0']*1000:.0f}}} = {set_res['delta_max_tri']:.2f} \\text{{ mm}}")
            st.latex(f"\\delta_{{max, \\text{{抛物}}}} = \\frac{{3 S_w}}{{x_0}} = \\frac{{3 \\times {set_res['Sw_mm2']:.0f}}}{{{set_res['x0']*1000:.0f}}} = {set_res['delta_max_para']:.2f} \\text{{ mm}}")

        with st.expander("步骤七：坑底抗隆起验算 (Prandtl)"):
            st.markdown(f"**抗隆起安全系数** (安全等级: {safety_level}, 限值: $K_{{he}} \\ge {factors['Khe']}$)")
            st.latex(f"N_q = e^{{\\pi \\tan \\varphi}} \\tan^2(45^\\circ + \\varphi/2) = {heave_res['Nq']:.2f}")
            st.latex(f"N_c = (N_q - 1) / \\tan \\varphi = {heave_res['Nc']:.2f}")
            st.markdown("桩底平面极限承载力 $p_{res}$ 与 滑动力 $p_{act}$：")
            st.latex(f"p_{{res}} = \\gamma_{{bot}} h_d N_q + c N_c = {heave_res['gamma_bot']:.1f} \\times {hd:.1f} \\times {heave_res['Nq']:.2f} + {heave_res['c']} \\times {heave_res['Nc']:.2f} = {heave_res['p_res']:.1f} \\text{{ kPa}}")
            st.latex(f"p_{{act}} = \\gamma_{{top}} (H_0 + h_d) + q = {heave_res['gamma_top_avg']:.1f} \\times {H0+hd:.1f} + {q} = {heave_res['p_act']:.1f} \\text{{ kPa}}")
            st.latex(f"K_{{he}} = \\frac{{p_{{res}}}}{{p_{{act}}}} = \\frac{{{heave_res['p_res']:.1f}}}{{{heave_res['p_act']:.1f}}} = {heave_res['Kl']:.3f}")
            
            if heave_res['Kl'] >= factors['Khe']:
                st.success(f"抗隆起稳定性满足规范 (Khe ≥ {factors['Khe']}) ✅")
            else:
                st.error(f"抗隆起不足 (Khe < {factors['Khe']}) ❌")

        with st.expander("步骤八：整体稳定性验算 (瑞典条分法)", expanded=True):
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

    # ---------------- 左侧：上下三幅图表联动 ----------------
    with col_chart:
        st.subheader("📊 综合受力与变形专题图")
        L = ov_res['L']
        x_max_plot = max(10, set_res['x0'] + 2)

        st.markdown("**图 1：地层排桩剖面与内力分布**")
        fig1 = make_subplots(rows=1, cols=3, shared_yaxes=True, subplot_titles=("<b>开挖剖面</b>", "<b>剪力 V (kN/m)</b>", "<b>弯矩 M (kN·m/m)</b>"), column_widths=[0.4, 0.3, 0.3], horizontal_spacing=0.03)
        draw_pit_profile(fig1, layer_stats, L, row=1, col=1, x_max=x_max_plot)
        fig1.add_trace(go.Scatter(x=forces_df['V'], y=forces_df['z'], mode='lines', name='剪力', line=dict(color='#ff7f0e', width=3), fill='tozerox', fillcolor='rgba(255, 127, 14, 0.2)'), row=1, col=2)
        fig1.add_vline(x=0, line_color="black", line_width=1, row=1, col=2)
        fig1.add_trace(go.Scatter(x=forces_df['M'], y=forces_df['z'], mode='lines', name='弯矩', line=dict(color='#2ca02c', width=3), fill='tozerox', fillcolor='rgba(44, 160, 44, 0.2)'), row=1, col=3)
        fig1.add_vline(x=0, line_color="black", line_width=1, row=1, col=3)
        fig1.update_layout(height=350, showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
        fig1.update_xaxes(range=[-x_max_plot, x_max_plot], showgrid=False, zeroline=False, showticklabels=False, row=1, col=1)
        fig1.update_yaxes(autorange="reversed", title_text="深度 (m)", row=1, col=1)
        st.plotly_chart(fig1, use_container_width=True)

        st.divider()

        st.markdown("**图 2：坑外地表沉降分析**")
        fig2 = go.Figure()
        draw_pit_profile(fig2, layer_stats, L, x_max=x_max_plot)
        scale_f = max(1, 1.5 / (set_res['delta_max_para'] / 1000)) if set_res['delta_max_para'] > 0 else 50
        y_plot_tri = set_res['y_tri'] / 1000 * scale_f
        y_plot_para = set_res['y_para'] / 1000 * scale_f
        fig2.add_trace(go.Scatter(x=set_res['x_set'], y=y_plot_tri, mode='lines', name='三角形法', line=dict(color='orange', width=2, dash='dash'), text=set_res['y_tri']))
        fig2.add_trace(go.Scatter(x=set_res['x_set'], y=y_plot_para, mode='lines', name='抛物线法', fill='tozeroy', fillcolor='rgba(214, 39, 40, 0.3)', line=dict(color='red', width=3), text=set_res['y_para']))
        fig2.update_layout(height=400, showlegend=True, legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99), margin=dict(l=10, r=10, t=10, b=10), xaxis_title="距基坑距离 X (m)", yaxis_title="深度 (m)")
        fig2.update_xaxes(range=[-x_max_plot, x_max_plot])
        fig2.update_yaxes(autorange="reversed")
        st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        st.markdown("**图 3：瑞典条分法整体稳定滑裂面**")
        fig3 = go.Figure()
        draw_pit_profile(fig3, layer_stats, L, x_max=x_max_plot)
        
        # 1. 仅绘制圆心位置
        fig3.add_trace(go.Scatter(x=[gs_res['xc']], y=[gs_res['zc']], mode='markers+text', marker=dict(size=8, color='black'), text=["圆心 O"], textposition="top right", name='滑裂圆心'))
        
        # 2. 绘制实际滑移段（地表以下）及切分带
        for slice_info in gs_res['slices_data']:
            x_m = slice_info['x_mid (m)']
            b_j = gs_res['b_slice']
            z_surf = 0 if x_m > 0 else H0
            z_arc = gs_res['zc'] + np.sqrt(gs_res['R']**2 - (x_m - gs_res['xc'])**2)
            # 绘制垂直切分线
            fig3.add_shape(type="line", x0=x_m - b_j/2, x1=x_m - b_j/2, y0=z_surf, y1=z_arc, line=dict(color="black", width=1, dash="dot"))

        # 3. 绘制底部加粗滑弧
        plot_z = gs_res['z_plot']
        plot_x = gs_res['x_plot']
        z_surf_arr = np.where(plot_x > 0, 0, H0)
        mask_underground = plot_z >= z_surf_arr
        if len(plot_x[mask_underground]) > 0:
            fig3.add_trace(go.Scatter(x=plot_x[mask_underground], y=plot_z[mask_underground], mode='lines', name='最危险滑裂面', line=dict(color='blue', width=4), hovertemplate="X: %{x:.1f} m<br>Z: %{y:.1f} m<extra></extra>"))
        
        fig3.update_layout(height=500, showlegend=False, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="距基坑距离 X (m)", yaxis_title="深度 (m)")
        fig3.update_xaxes(range=[-x_max_plot, x_max_plot])
        
        z_top_limit = min(-2, gs_res['zc'] - 2)
        fig3.update_yaxes(autorange="reversed", range=[L + 5, z_top_limit])
        st.plotly_chart(fig3, use_container_width=True)