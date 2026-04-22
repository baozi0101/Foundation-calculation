import streamlit as st
import pandas as pd

# ================= 1. 全局默认基坑参数 =================
DEFAULT_PIT_PARAMS = {
    'H0': 6.15,   
    'zw_out': 20.0,  # <--- 【修改点】：地下水位改为坑外水位
    'zw_in': 15.0,    # <--- 【修改点】：增加坑内水位，默认20
    'q': 20.0,   
    'hd': 7.35,
    'safety_level': '二级'  # 新增安全等级默认值    
}

# ================= 2. 全局默认土层参数 =================
DEFAULT_SOIL_DATA = {
    '地层编号': ['①', '②', '③', '④'],
    '土层名称': ['填土层', '粉质黏土层', '粉土层', '圆砾层'],
    '厚度(m)': [4.2, 4.6, 3.2, 1.5], 
    '天然重度(kN/m³)': [19, 19.5, 19, 18.5],
    '饱和重度(kN/m³)': [19.5, 20.3, 20.8, 20.8],
    '黏聚力c(kPa)': [20.0, 42.0, 25.0, 21.0],
    '内摩擦角φ(°)': [10.0, 12.0, 10.0, 8.0],
    '极限粘结强度(kPa)': [20.0, 35.0, 60.0, 80.0],
    '计算模式': ['水土合算', '水土合算', '水土合算', '水土合算']
    
}

# ================= 3. 状态初始化管理器 =================
def init_global_state():
    """
    建立独立于 UI 组件的永久状态池。
    哪怕页面切换导致组件被销毁，这些核心数据依然安全地保存在内存中。
    """
    # 【修复点】：变量名已经去掉了 global_ 前缀，与页面代码严格对应
    if 'H0' not in st.session_state: 
        st.session_state.H0 = DEFAULT_PIT_PARAMS['H0']
    if 'zw_out' not in st.session_state:  # <--- 【修改点】
        st.session_state.zw_out = DEFAULT_PIT_PARAMS['zw_out']
    if 'zw_in' not in st.session_state:   # <--- 【修改点】
        st.session_state.zw_in = DEFAULT_PIT_PARAMS['zw_in']
    if 'q' not in st.session_state: 
        st.session_state.q = DEFAULT_PIT_PARAMS['q']
    if 'hd' not in st.session_state: 
        st.session_state.hd = DEFAULT_PIT_PARAMS['hd']
    if 'safety_level' not in st.session_state: 
        st.session_state.safety_level = DEFAULT_PIT_PARAMS['safety_level']
        
    # 土层表格数据比较特殊，保持原名
    if 'global_soil_df' not in st.session_state:
        st.session_state.global_soil_df = pd.DataFrame(DEFAULT_SOIL_DATA)
    else:
        # 如果缺列，或者所有值都被防错机制填成了 40.0，则重置为阶梯值
        df = st.session_state.global_soil_df
        if '极限粘结强度(kPa)' not in df.columns or (df['极限粘结强度(kPa)'] == 40.0).all():
            default_qsik = DEFAULT_SOIL_DATA['极限粘结强度(kPa)']
            # 按照当前表格的行数动态赋值
            df['极限粘结强度(kPa)'] = [default_qsik[i] if i < len(default_qsik) else 40.0 for i in range(len(df))]
            st.session_state.global_soil_df = df
    if 'selected_layer' not in st.session_state: 
        st.session_state.selected_layer = None