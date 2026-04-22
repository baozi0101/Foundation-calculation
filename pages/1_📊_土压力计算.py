import streamlit as st
import plotly.graph_objects as go

from components.inputs import render_soil_editor
from core.soil_mechanics import calculate_earth_pressure
from utils.config import init_global_state

st.set_page_config(page_title="土压力计算", layout="wide")

# ================= 1. 全局状态初始化 =================
init_global_state()

st.title("📊 朗肯土压力交互式计算模块")

# ================= 2. 侧边栏与参数输入 =================
with st.sidebar:
    st.header("⚙️ 基坑与环境参数")
    st.session_state.H0 = st.number_input("基坑深度 H0 (m)", value=st.session_state.H0, step=0.5)
    st.session_state.zw = st.number_input("地下水位 zw (m)", value=st.session_state.zw, step=0.5)
    st.session_state.q = st.number_input("地表超载 q (kPa)", value=st.session_state.q, step=5.0)
    
    H0 = st.session_state.H0
    zw = st.session_state.zw
    q = st.session_state.q

# ================= 3. 获取全局土层数据 =================
df_soil = render_soil_editor()

# ================= 4. 核心计算与图表渲染 =================
if not df_soil.empty:
    calc_df, layer_stats = calculate_earth_pressure(df_soil, H0, zw, q)

    st.markdown("---")
    col_chart, col_process = st.columns([1.2, 1])
    
    with col_process:
        st.subheader("🧮 分层计算过程展示")
        
        for stat in layer_stats:
            # 【修复点】：在这里对 top 和 bot 强制保留两位小数
            with st.expander(f"📌 {stat['layer_id']} {stat['name']} (深度 {stat['top']:.2f}m ~ {stat['bot']:.2f}m)", expanded=False):
                st.markdown(f"**【本层物理力学参数】**\n"
                            f"* $\\gamma = {stat['gamma_nat']}$ kN/m³ (天然) | $\\gamma_{{sat}} = {stat['gamma_sat']}$ kN/m³ (饱和)\n"
                            f"* $c = {stat['c']}$ kPa | $\\varphi = {stat['phi']}^\\circ$\n"
                            f"* 计算模式：`{stat['mode']}`")
                st.divider()
                
                c = stat['c']
                
                if stat['mode'] == '水土分算':
                    st.markdown("**(1) 孔隙水压力计算 (水土分算)**")
                    if stat['u_bot'] > 0:
                        st.latex(f"u_{{top}} = \\max(0, \\gamma_w (z_{{top}} - z_w)) = {stat['u_top']:.2f} \\text{{ kPa}}")
                        st.latex(f"u_{{bot}} = \\max(0, \\gamma_w (z_{{bot}} - z_w)) = {stat['u_bot']:.2f} \\text{{ kPa}}")
                    else:
                        st.latex("u = 0 \\text{ kPa (位于水位以上)}")
                else:
                    st.markdown("**(1) 孔隙水压力计算**")
                    st.latex("u_{top} = 0 \\text{ kPa}, \\quad u_{bot} = 0 \\text{ kPa} \\quad \\text{(水土合算)}")
                
                st.markdown("**(2) 主动土压力强度 ($e_a$)**")
                st.latex(f"\\sigma'_{{v,top}} = {stat['sigma_a_top']:.2f} \\text{{ kPa}}, \\quad \\sigma'_{{v,bot}} = {stat['sigma_a_bot']:.2f} \\text{{ kPa}}")
                st.latex(f"K_a = \\tan^2(45^\\circ - {stat['phi']}/2) = {stat['Ka']:.3f}")
                
                st.markdown("顶面土骨架有效土压力 (未截断)：")
                st.latex(f"e_{{a,top(soil)}} = \\sigma'_{{v,top}} K_a - 2c\\sqrt{{K_a}}")
                st.latex(f"= {stat['sigma_a_top']:.2f} \\times {stat['Ka']:.3f} - 2 \\times {c} \\times \\sqrt{{{stat['Ka']:.3f}}} = {stat['ea_soil_top_uncapped']:.2f} \\text{{ kPa}}")
                
                if stat['has_tension']:
                    st.info(f"💡 $e_{{a,top(soil)}} = {stat['ea_soil_top_uncapped']:.2f} < 0$，该处土体受拉开裂，取 0。")
                
                st.latex(f"e_{{a,top}} = \\max(0, e_{{a,top(soil)}}) + u_{{top}}")
                st.latex(f"= \\max(0, {stat['ea_soil_top_uncapped']:.2f}) + {stat['u_top']:.2f} = {stat['ea_top']:.2f} \\text{{ kPa}}")
                
                st.markdown("底面土骨架有效土压力 (未截断)：")
                st.latex(f"e_{{a,bot(soil)}} = \\sigma'_{{v,bot}} K_a - 2c\\sqrt{{K_a}} = {stat['ea_soil_bot_uncapped']:.2f} \\text{{ kPa}}")
                st.latex(f"e_{{a,bot}} = \\max(0, e_{{a,bot(soil)}}) + u_{{bot}} = {stat['ea_bot']:.2f} \\text{{ kPa}}")
                
                st.markdown("**(3) 主动土压力合力与作用点**")
                if stat['has_tension'] and stat['zc'] < stat['bot']:
                    st.markdown("根据相似三角形插值计算**临界开裂深度 $z_c$**：")
                    st.latex(f"z_c = {stat['top']:.2f} + \\frac{{|{stat['ea_soil_top_uncapped']:.2f}|}}{{|{stat['ea_soil_top_uncapped']:.2f}| + {stat['ea_soil_bot_uncapped']:.2f}}} \\times {stat['dz']:.2f} = {stat['zc']:.2f} \\text{{ m}}")
                    Lc = stat['bot'] - stat['zc']
                    if stat['mode'] == '水土合算' or (stat['mode'] == '水土分算' and stat['u_bot'] == 0):
                        st.latex(f"E_a = \\frac{{1}}{{2}} e_{{a,bot}} L_c = \\frac{{1}}{{2}} \\times {stat['ea_bot']:.2f} \\times {Lc:.2f} = {stat['Ea']:.2f} \\text{{ kN/m}}")
                    else:
                        st.latex(f"E_a = E_{{a(soil)}} + E_w = {stat['Ea']:.2f} \\text{{ kN/m}}")
                elif stat['has_tension'] and stat['zc'] >= stat['bot']:
                    st.latex("E_a = 0 \\text{ kN/m}")
                else:
                    st.latex(f"E_a = \\frac{{{stat['ea_top']:.2f} + {stat['ea_bot']:.2f}}}{{2}} \\times {stat['dz']:.2f} = {stat['Ea']:.2f} \\text{{ kN/m}}")
                    
                if stat['Ea'] > 0:
                    st.latex(f"z_a = {stat['za']:.2f} \\text{{ m}} \\quad \\text{{(距地表深度)}}")

                if stat['Ep'] > 0:
                    st.divider()
                    st.markdown("**(4) 被动土压力强度 ($e_p$)**")
                    st.info("💡 该层跨越或位于基坑底，以下参数仅针对**坑底及以下**的被动区提取：")
                    
                    st.latex(f"K_p = \\tan^2(45^\\circ + {stat['phi']}/2) = {stat['Kp']:.3f}")
                    st.latex(f"\\sigma'_{{v,top(pas)}} = {stat['sigma_p_top']:.2f} \\text{{ kPa}}, \\quad \\sigma'_{{v,bot(pas)}} = {stat['sigma_p_bot']:.2f} \\text{{ kPa}}")
                    
                    st.latex(f"e_{{p,top}} = \\sigma'_{{v,top(pas)}} K_p + 2c\\sqrt{{K_p}} + u_{{p,top}}")
                    st.latex(f"= {stat['sigma_p_top']:.2f} \\times {stat['Kp']:.3f} + 2 \\times {c} \\times \\sqrt{{{stat['Kp']:.3f}}} + {stat['u_p_top']:.2f} = {stat['ep_top']:.2f} \\text{{ kPa}}")
                    
                    st.latex(f"e_{{p,bot}} = \\sigma'_{{v,bot(pas)}} K_p + 2c\\sqrt{{K_p}} + u_{{p,bot}}")
                    st.latex(f"= {stat['sigma_p_bot']:.2f} \\times {stat['Kp']:.3f} + 2 \\times {c} \\times \\sqrt{{{stat['Kp']:.3f}}} + {stat['u_p_bot']:.2f} = {stat['ep_bot']:.2f} \\text{{ kPa}}")
                    
                    st.markdown("**(5) 被动土压力合力与作用点**")
                    st.latex(f"E_p \\approx \\frac{{{stat['ep_top']:.2f} + {stat['ep_bot']:.2f}}}{{2}} \\times {stat['dz_p']:.2f} = {stat['Ep']:.2f} \\text{{ kN/m}}")
                    st.latex(f"z_p = {stat['zp']:.2f} \\text{{ m}}")

                if st.button(f"🎯 在图中标出 {stat['layer_id']} 层合力", key=f"btn_ep_{stat['layer_id']}"):
                    st.session_state.selected_layer = stat['layer_id']
                    st.rerun()

    with col_chart:
        st.subheader("📊 基坑开挖与土压力分布图")
        
        colors = ['#f4f1de', '#e07a5f', '#3d405b', '#81b29a', '#f2cc8f', '#e5989b', '#98c1d9']
        fig = go.Figure()
        
        max_ea = calc_df['ea'].max()
        max_ep = calc_df['ep'].max()
        x_right_bound = max_ea * 1.2 if max_ea > 0 else 50
        x_left_bound = -max_ep * 1.2 if max_ep > 0 else -50
        
        for i, stat in enumerate(layer_stats):
            color = colors[i % len(colors)]
            opacity = 0.25 
            
            fig.add_shape(type="rect", x0=0, y0=stat['top'], x1=x_right_bound, y1=stat['bot'],
                          fillcolor=color, opacity=opacity, layer="below", line_width=0)
            fig.add_shape(type="line", x0=0, y0=stat['bot'], x1=x_right_bound, y1=stat['bot'],
                          line=dict(color="gray", width=1, dash="dot"))

            if stat['bot'] > H0:
                y_top_passive = max(stat['top'], H0) 
                fig.add_shape(type="rect", x0=x_left_bound, y0=y_top_passive, x1=0, y1=stat['bot'],
                              fillcolor=color, opacity=opacity, layer="below", line_width=0)
                fig.add_shape(type="line", x0=x_left_bound, y0=stat['bot'], x1=0, y1=stat['bot'],
                              line=dict(color="gray", width=1, dash="dot"))
                
        fig.add_trace(go.Scatter(
            x=calc_df['ea'], y=calc_df['z'], mode='lines', name='主动土压力',
            line=dict(color='#d62728', width=3), fill='tozerox', fillcolor='rgba(214, 39, 40, 0.3)',
            hovertemplate="<b>深度:</b> %{y:.2f} m<br><b>主动土压力:</b> %{x:.2f} kPa<extra></extra>"
        ))
        
        fig.add_trace(go.Scatter(
            x=-calc_df['ep'], y=calc_df['z'], mode='lines', name='被动土压力',
            line=dict(color='#1f77b4', width=3), fill='tozerox', fillcolor='rgba(31, 119, 180, 0.3)',
            hovertemplate="<b>深度:</b> %{y:.2f} m<br><b>被动土压力:</b> %{text} kPa<extra></extra>",
            text=calc_df['ep'].round(2) 
        ))

        fig.add_hline(y=H0, line_dash="dash", line_color="green", line_width=2, annotation_text=f"基坑底 H={H0}m", annotation_position="bottom left")
        fig.add_hline(y=zw, line_dash="dashdot", line_color="blue", annotation_text=f"地下水 zw={zw}m", annotation_position="bottom right")
        fig.add_vline(x=0, line_color="black", line_width=2)

        hl_id = st.session_state.selected_layer
        if hl_id:
            hl_stat = next((s for s in layer_stats if s['layer_id'] == hl_id), None)
            if hl_stat and hl_stat['Ea'] > 0:
                fig.add_annotation(
                    x=0, y=hl_stat['za'], ax=max_ea*0.6, ay=hl_stat['za'], xref="x", yref="y", axref="x", ayref="y",
                    text=f"<b>Ea = {hl_stat['Ea']:.1f} kN/m</b>", showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5, arrowcolor="#d62728", font=dict(size=15, color="#d62728"), xanchor="left", yanchor="bottom"
                )
            if hl_stat and hl_stat['Ep'] > 0:
                fig.add_annotation(
                    x=0, y=hl_stat['zp'], ax=-max_ep*0.6, ay=hl_stat['zp'], xref="x", yref="y", axref="x", ayref="y",
                    text=f"<b>Ep = {hl_stat['Ep']:.1f} kN/m</b>", showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5, arrowcolor="#1f77b4", font=dict(size=15, color="#1f77b4"), xanchor="right", yanchor="bottom"
                )

        fig.update_layout(yaxis_autorange="reversed", xaxis_title="<b>土压力 (kPa)</b>", yaxis_title="<b>深度 (m)</b>", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01), margin=dict(l=20, r=20, t=30, b=20), hovermode="y unified", height=700)
        st.plotly_chart(fig, use_container_width=True)

        if st.button("🔄 清除图表上的合力标注"):
            st.session_state.selected_layer = None
            st.rerun()