import streamlit as st
import pandas as pd

# ================= 1. 全局默认基坑参数 =================
DEFAULT_PIT_PARAMS = {
    'H0': 6.15,   
    'zw': 20.0,   
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
    if 'zw' not in st.session_state: 
        st.session_state.zw = DEFAULT_PIT_PARAMS['zw']
    if 'q' not in st.session_state: 
        st.session_state.q = DEFAULT_PIT_PARAMS['q']
    if 'hd' not in st.session_state: 
        st.session_state.hd = DEFAULT_PIT_PARAMS['hd']
    if 'safety_level' not in st.session_state: 
        st.session_state.safety_level = DEFAULT_PIT_PARAMS['safety_level']
        
    # 土层表格数据比较特殊，保持原名
    if 'global_soil_df' not in st.session_state:
        st.session_state.global_soil_df = pd.DataFrame(DEFAULT_SOIL_DATA)
        
    if 'selected_layer' not in st.session_state: 
        st.session_state.selected_layer = None