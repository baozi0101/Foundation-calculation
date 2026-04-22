import streamlit as st
import pandas as pd
from utils.config import DEFAULT_SOIL_DATA

def render_soil_editor():
    st.subheader("📝 土层物理力学参数输入")

    column_config = {
        "计算模式": st.column_config.SelectboxColumn(
            "计算模式", help="选择水土合算或分算", options=["水土合算", "水土分算"], required=True
        ),
        # <--- 【新增列UI配置】：规范化显示格式
        "极限粘结强度(kPa)": st.column_config.NumberColumn(
            "极限粘结强度(kPa)", help="用于土钉墙或锚杆抗拔承载力计算", step=5.0
        )
    }

    edited_df = st.data_editor(
        st.session_state.global_soil_df, 
        num_rows="dynamic",
        column_config=column_config, 
        use_container_width=True
    )

    if len(edited_df) > 0:
        for i in range(len(edited_df)):
            if pd.isna(edited_df.iloc[i]['地层编号']) or edited_df.iloc[i]['地层编号'] == "":
                edited_df.at[edited_df.index[i], '地层编号'] = f"新{i+1}"
            if pd.isna(edited_df.iloc[i]['土层名称']) or edited_df.iloc[i]['土层名称'] == "":
                edited_df.at[edited_df.index[i], '土层名称'] = '黏土'
            if pd.isna(edited_df.iloc[i]['计算模式']) or edited_df.iloc[i]['计算模式'] == "":
                edited_df.at[edited_df.index[i], '计算模式'] = '水土合算'
                
            # <--- 【新增】：如果用户新建了一行，自动赋初值为 40.0 kPa
            if '极限粘结强度(kPa)' in edited_df.columns:
                if pd.isna(edited_df.iloc[i]['极限粘结强度(kPa)']):
                    edited_df.at[edited_df.index[i], '极限粘结强度(kPa)'] = 40.0
        
        st.session_state.global_soil_df = edited_df

    return edited_df