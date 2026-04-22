import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ================= 1. 页面基本配置 =================
st.set_page_config(page_title="基坑计算系统 V3", layout="wide")
st.title("🏗️ 基坑支护：交互式土压力计算与验证系统")

# 初始化 Session State 用于显示合力联动
if 'selected_layer' not in st.session_state:
    st.session_state.selected_layer = None

# ================= 2. 侧边栏与基础参数 =================
with st.sidebar:
    st.header("⚙️ 基坑与环境参数")
    H0 = st.number_input("基坑深度 H0 (m)", value=8.0, step=0.5)
    zw = st.number_input("地下水位 zw (m)", value=2.0, step=0.5)
    q = st.number_input("地表超载 q (kPa)", value=20.0, step=5.0)
    gamma_w = 10.0  # 水的重度

# ================= 3. 可编辑数据表格 =================
st.subheader("📝 土层物理力学参数输入")

default_data = {
    '地层编号': ['①', '②', '③', '④', '⑤'],
    '土层名称': ['填土层', '粉质黏土层', '粉土层', '圆砾层', '强风化泥岩层'],
    '层底深度(m)': [1.1, 5.4, 6.8, 10.2, 14.4],
    '天然重度(kN/m³)': [18.8, 19.8, 20.1, 24.0, 21.2],
    '饱和重度(kN/m³)': [19.5, 20.3, 20.8, 24.8, 21.8],
    '黏聚力c(kPa)': [6.0, 15.0, 8.0, 0.0, 22.0],
    '内摩擦角φ(°)': [12.0, 17.0, 25.0, 38.0, 23.0],
    '计算模式': ['水土合算', '水土合算', '水土分算', '水土合算', '水土合算']
}
if 'df_data' not in st.session_state:
    st.session_state.df_data = pd.DataFrame(default_data)

column_config = {
    "计算模式": st.column_config.SelectboxColumn(
        "计算模式", help="选择水土合算或分算", options=["水土合算", "水土分算"], required=True
    )
}

edited_df = st.data_editor(
    st.session_state.df_data, num_rows="dynamic",
    column_config=column_config, use_container_width=True, key="editor"
)

# 自动处理新增行的默认值填充逻辑
if len(edited_df) > 0:
    for i in range(len(edited_df)):
        if pd.isna(edited_df.iloc[i]['地层编号']) or edited_df.iloc[i]['地层编号'] == "":
            edited_df.at[edited_df.index[i], '地层编号'] = f"新{i+1}"
        if pd.isna(edited_df.iloc[i]['土层名称']) or edited_df.iloc[i]['土层名称'] == "":
            edited_df.at[edited_df.index[i], '土层名称'] = '黏土'
        if pd.isna(edited_df.iloc[i]['计算模式']) or edited_df.iloc[i]['计算模式'] == "":
            edited_df.at[edited_df.index[i], '计算模式'] = '水土合算'
    st.session_state.df_data = edited_df

# ================= 4. 核心计算引擎 =================
@st.cache_data
def calculate_earth_pressure(df, H0, zw, q):
    max_depth = df['层底深度(m)'].max()
    nodes = np.arange(0, max_depth + 0.05, 0.05) 
    important_nodes = df['层底深度(m)'].tolist() + [zw, H0, 0]
    all_depths = np.unique(np.sort(np.append(nodes, important_nodes)))
    
    results = []
    sigma_v_act, sigma_v_pas = q, 0
    prev_z = 0
    
    for z in all_depths:
        layer_idx = df.index[df['层底深度(m)'] >= z].min()
        if pd.isna(layer_idx): layer_idx = df.index[-1]
        layer = df.loc[layer_idx]
        
        c, phi = layer['黏聚力c(kPa)'], layer['内摩擦角φ(°)']
        mode = layer['计算模式']
        dz = z - prev_z
        
        if mode == '水土分算':
            gamma_calc = layer['天然重度(kN/m³)'] if z <= zw else (layer['饱和重度(kN/m³)'] - gamma_w)
            u = max(0, (z - zw) * gamma_w)
        else:
            gamma_calc = layer['天然重度(kN/m³)'] if z <= zw else layer['饱和重度(kN/m³)']
            u = 0
            
        sigma_v_act += gamma_calc * dz
        if z > H0: sigma_v_pas += gamma_calc * dz
            
        Ka = np.tan(np.radians(45 - phi/2))**2
        Kp = np.tan(np.radians(45 + phi/2))**2
        
        ea = max(0, sigma_v_act * Ka - 2 * c * np.sqrt(Ka)) + u
        ep = (sigma_v_pas * Kp + 2 * c * np.sqrt(Kp)) + u if z >= H0 else 0
        
        results.append({
            'z': z, 'layer_id': layer['地层编号'], 'layer_name': layer['土层名称'],
            'sigma_a': sigma_v_act, 'sigma_p': sigma_v_pas, 'u': u,
            'Ka': Ka, 'Kp': Kp, 'ea': ea, 'ep': ep
        })
        prev_z = z
        
    calc_df = pd.DataFrame(results)
    
    layer_stats = []
    top_z = 0
    for idx, row in df.iterrows():
        bot_z = row['层底深度(m)']
        mask = (calc_df['z'] >= top_z) & (calc_df['z'] <= bot_z)
        slice_df = calc_df[mask]
        
        z_arr = slice_df['z'].values
        ea_arr = slice_df['ea'].values
        Ea = np.trapz(ea_arr, z_arr)
        za = np.trapz(z_arr * ea_arr, z_arr) / Ea if Ea > 0 else 0
        
        ep_arr = slice_df['ep'].values
        Ep = np.trapz(ep_arr, z_arr)
        zp = np.trapz(z_arr * ep_arr, z_arr) / Ep if Ep > 0 else 0
        
        layer_stats.append({
            'layer_id': row['地层编号'], 'name': row['土层名称'],
            'top': top_z, 'bot': bot_z,
            'ea_top': ea_arr[0], 'ea_bot': ea_arr[-1],
            'ep_top': ep_arr[0], 'ep_bot': ep_arr[-1],
            'Ka': slice_df['Ka'].iloc[0], 'Kp': slice_df['Kp'].iloc[0],
            'Ea': Ea, 'za': za, 'Ep': Ep, 'zp': zp
        })
        top_z = bot_z
        
    return calc_df, layer_stats

# ================= 5. 图表与过程展示 =================
if not edited_df.empty:
    calc_df, layer_stats = calculate_earth_pressure(edited_df, H0, zw, q)

    st.markdown("---")
    col_chart, col_process = st.columns([1.2, 1])
    
    # -------- 右侧：分层计算过程 --------
    with col_process:
        st.subheader("🧮 分层计算过程展示")
        
        for stat in layer_stats:
            with st.expander(f"📌 {stat['layer_id']} {stat['name']} (深度 {stat['top']}m ~ {stat['bot']}m)", expanded=True):
                st.latex(f"K_a = \\tan^2(45^\\circ - \\varphi/2) = {stat['Ka']:.3f}")
                st.markdown(f"**顶面 (z={stat['top']}m):**")
                st.latex(f"e_{{a,\\text{{top}}}} = \\sigma_{{v,\\text{{top}}}} K_a - 2c\\sqrt{{K_a}} + u = {stat['ea_top']:.2f} \\text{{ kPa}}")
                st.markdown(f"**底面 (z={stat['bot']}m):**")
                st.latex(f"e_{{a,\\text{{bot}}}} = \\sigma_{{v,\\text{{bot}}}} K_a - 2c\\sqrt{{K_a}} + u = {stat['ea_bot']:.2f} \\text{{ kPa}}")
                
                st.markdown(f"🌟 **主动土压力合力:** $E_a$ = **{stat['Ea']:.2f} kN/m**")
                if stat['Ea'] > 0:
                    st.markdown(f"🎯 **合力作用点深度:** $z_a$ = **{stat['za']:.2f} m**")
                
                if stat['Ep'] > 0:
                    st.markdown(f"🌟 **被动土压力合力:** $E_p$ = **{stat['Ep']:.2f} kN/m** (作用点 $z_p$={stat['zp']:.2f}m)")
                
                # 交互按钮：只显示受力箭头，不再整体高亮色块
                if st.button(f"🎯 在图中标出 {stat['layer_id']} 层合力", key=f"btn_{stat['layer_id']}"):
                    st.session_state.selected_layer = stat['layer_id']
                    st.rerun()

    # -------- 左侧：交互式 Plotly 图表 --------
    with col_chart:
        st.subheader("📊 基坑开挖与土压力分布图")
        
        colors = ['#f4f1de', '#e07a5f', '#3d405b', '#81b29a', '#f2cc8f', '#e5989b', '#98c1d9']
        
        fig = go.Figure()
        max_ea = calc_df['ea'].max()
        max_ep = calc_df['ep'].max()
        
        # 为了保证左右侧矩形和线条边界对齐，提取绘图极值
        x_right_bound = max_ea * 1.2 if max_ea > 0 else 50
        x_left_bound = -max_ep * 1.2 if max_ep > 0 else -50
        
        # 1. 绘制背景色块和土层分界线 (已挖空左侧基坑以上区域)
        for i, stat in enumerate(layer_stats):
            color = colors[i % len(colors)]
            opacity = 0.25 # 固定的背景透明度，不再随点击变化
            
            # 【右侧主动区】
            # 背景色块
            fig.add_shape(type="rect", x0=0, y0=stat['top'], x1=x_right_bound, y1=stat['bot'],
                          fillcolor=color, opacity=opacity, layer="below", line_width=0)
            # 土层底部水平分界线
            fig.add_shape(type="line", x0=0, y0=stat['bot'], x1=x_right_bound, y1=stat['bot'],
                          line=dict(color="gray", width=1, dash="dot"))

            # 【左侧被动区】(仅在基坑底 H0 以下绘制)
            if stat['bot'] > H0:
                y_top_passive = max(stat['top'], H0) # 从基坑底或本层顶面开始
                # 背景色块
                fig.add_shape(type="rect", x0=x_left_bound, y0=y_top_passive, x1=0, y1=stat['bot'],
                              fillcolor=color, opacity=opacity, layer="below", line_width=0)
                # 土层底部水平分界线
                fig.add_shape(type="line", x0=x_left_bound, y0=stat['bot'], x1=0, y1=stat['bot'],
                              line=dict(color="gray", width=1, dash="dot"))
                
        # 2. 绘制主动土压力线 (右侧)
        fig.add_trace(go.Scatter(
            x=calc_df['ea'], y=calc_df['z'], 
            mode='lines', name='主动土压力',
            line=dict(color='#d62728', width=3),
            fill='tozerox', fillcolor='rgba(214, 39, 40, 0.3)',
            hovertemplate="<b>深度:</b> %{y:.2f} m<br><b>主动土压力:</b> %{x:.2f} kPa<extra></extra>"
        ))
        
        # 3. 绘制被动土压力线 (左侧)
        fig.add_trace(go.Scatter(
            x=-calc_df['ep'], y=calc_df['z'], 
            mode='lines', name='被动土压力',
            line=dict(color='#1f77b4', width=3),
            fill='tozerox', fillcolor='rgba(31, 119, 180, 0.3)',
            hovertemplate="<b>深度:</b> %{y:.2f} m<br><b>被动土压力:</b> %{text} kPa<extra></extra>",
            text=calc_df['ep'].round(2) 
        ))

        # 4. 绘制开挖线、地下水位线和零点轴
        fig.add_hline(y=H0, line_dash="dash", line_color="green", line_width=2, annotation_text=f"基坑底 H={H0}m", annotation_position="bottom left")
        fig.add_hline(y=zw, line_dash="dashdot", line_color="blue", annotation_text=f"地下水 zw={zw}m", annotation_position="bottom right")
        fig.add_vline(x=0, line_color="black", line_width=2)

        # 5. 根据按钮点击状态，仅在指定位置添加合力箭头和数值
        hl_id = st.session_state.selected_layer
        if hl_id:
            hl_stat = next((s for s in layer_stats if s['layer_id'] == hl_id), None)
            if hl_stat and hl_stat['Ea'] > 0:
                fig.add_annotation(
                    x=0, y=hl_stat['za'], ax=max_ea*0.6, ay=hl_stat['za'],
                    xref="x", yref="y", axref="x", ayref="y",
                    text=f"<b>Ea = {hl_stat['Ea']:.1f} kN/m</b>", showarrow=True,
                    arrowhead=3, arrowsize=1.5, arrowwidth=2.5, arrowcolor="#d62728",
                    font=dict(size=15, color="#d62728"), xanchor="left", yanchor="bottom"
                )
            if hl_stat and hl_stat['Ep'] > 0:
                fig.add_annotation(
                    x=0, y=hl_stat['zp'], ax=-max_ep*0.6, ay=hl_stat['zp'],
                    xref="x", yref="y", axref="x", ayref="y",
                    text=f"<b>Ep = {hl_stat['Ep']:.1f} kN/m</b>", showarrow=True,
                    arrowhead=3, arrowsize=1.5, arrowwidth=2.5, arrowcolor="#1f77b4",
                    font=dict(size=15, color="#1f77b4"), xanchor="right", yanchor="bottom"
                )

        # 6. 图表样式布局调整
        fig.update_layout(
            yaxis_autorange="reversed", 
            xaxis_title="<b>土压力 (kPa)</b>",
            yaxis_title="<b>深度 (m)</b>",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
            margin=dict(l=20, r=20, t=30, b=20),
            hovermode="y unified", 
            height=700
        )
        
        st.plotly_chart(fig, use_container_width=True)

        if st.button("🔄 清除图表上的合力标注"):
            st.session_state.selected_layer = None
            st.rerun()