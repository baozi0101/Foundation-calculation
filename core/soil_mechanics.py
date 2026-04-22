import numpy as np
import pandas as pd
import streamlit as st

@st.cache_data
def calculate_earth_pressure(df, H0, zw, q, gamma_w=10.0):
    df = df.copy()
    df['层底深度(m)'] = df['厚度(m)'].cumsum()
    
    results = []
    layer_stats = []
    
    sigma_v_act = q
    sigma_v_pas = 0
    top_z = 0
    
    for idx, row in df.iterrows():
        bot_z = row['层底深度(m)']
        if bot_z <= top_z: continue 
        
        c, phi = row['黏聚力c(kPa)'], row['内摩擦角φ(°)']
        mode = row['计算模式']
        gamma_nat, gamma_sat = row['天然重度(kN/m³)'], row['饱和重度(kN/m³)']
        
        Ka = np.tan(np.radians(45 - phi/2))**2
        Kp = np.tan(np.radians(45 + phi/2))**2
        
        layer_nodes = [top_z, bot_z]
        if top_z < zw < bot_z: layer_nodes.append(zw)
        if top_z < H0 < bot_z: layer_nodes.append(H0)
        
        step_nodes = np.arange(top_z, bot_z + 0.05, 0.05)
        layer_depths = np.unique(np.sort(np.append(step_nodes, layer_nodes)))
        
        layer_df_rows = []
        
        for i, z in enumerate(layer_depths):
            dz = z - layer_depths[i-1] if i > 0 else 0
            
            if mode == '水土分算':
                gamma_calc = gamma_nat if (z - dz/2) <= zw else (gamma_sat - gamma_w)
                u = max(0, (z - zw) * gamma_w)
            else:
                gamma_calc = gamma_nat if (z - dz/2) <= zw else gamma_sat
                u = 0
                
            sigma_v_act += gamma_calc * dz
            if (z - dz/2) > H0:
                sigma_v_pas += gamma_calc * dz
                
            ea_soil = sigma_v_act * Ka - 2 * c * np.sqrt(Ka)
            ea = max(0, ea_soil) + u
            
            # 被动土压力仅在基坑底及以下产生
            ep = (sigma_v_pas * Kp + 2 * c * np.sqrt(Kp)) + u if z >= H0 else 0
            
            row_dict = {
                'z': z, 'layer_id': row['地层编号'], 'layer_name': row['土层名称'],
                'sigma_a': sigma_v_act, 'sigma_p': sigma_v_pas, 'u': u,
                'Ka': Ka, 'Kp': Kp, 'ea': ea, 'ep': ep,
                'ea_soil_uncapped': ea_soil
            }
            results.append(row_dict)
            layer_df_rows.append(row_dict)
            
        layer_df = pd.DataFrame(layer_df_rows)
        
        # ---------------- 1. 主动土压力合力提取 ----------------
        ea_arr = layer_df['ea'].values
        z_arr = layer_df['z'].values
        Ea = np.trapz(ea_arr, z_arr)
        za = np.trapz(z_arr * ea_arr, z_arr) / Ea if Ea > 0 else 0
        
        ea_soil_top = layer_df['ea_soil_uncapped'].iloc[0]
        ea_soil_bot = layer_df['ea_soil_uncapped'].iloc[-1]
        has_tension = False
        zc = top_z
        
        if ea_soil_top < 0:
            has_tension = True
            if ea_soil_bot > 0:
                zc = top_z + (bot_z - top_z) * abs(ea_soil_top) / (abs(ea_soil_top) + ea_soil_bot)
            else:
                zc = bot_z
                
        # ---------------- 2. 被动土压力合力提取 (严格限缩于被动区) ----------------
        df_pas = layer_df[layer_df['z'] >= H0]
        if not df_pas.empty and bot_z > H0:
            ep_arr_pas = df_pas['ep'].values
            z_arr_pas = df_pas['z'].values
            Ep = np.trapz(ep_arr_pas, z_arr_pas)
            zp = np.trapz(z_arr_pas * ep_arr_pas, z_arr_pas) / Ep if Ep > 0 else 0
            
            sigma_p_top = df_pas['sigma_p'].iloc[0]
            sigma_p_bot = df_pas['sigma_p'].iloc[-1]
            u_p_top = df_pas['u'].iloc[0]
            u_p_bot = df_pas['u'].iloc[-1]
            ep_top = df_pas['ep'].iloc[0]
            ep_bot = df_pas['ep'].iloc[-1]
            dz_p = bot_z - df_pas['z'].iloc[0] # 被动区的实际厚度
        else:
            Ep = zp = 0
            sigma_p_top = sigma_p_bot = u_p_top = u_p_bot = ep_top = ep_bot = dz_p = 0
                
        layer_stats.append({
            'layer_id': row['地层编号'], 'name': row['土层名称'],
            'mode': mode, 'c': c, 'phi': phi, 'gamma_nat': gamma_nat, 'gamma_sat': gamma_sat,
            'top': top_z, 'bot': bot_z, 'dz': bot_z - top_z,
            # 主动区特征点
            'sigma_a_top': layer_df['sigma_a'].iloc[0], 'sigma_a_bot': layer_df['sigma_a'].iloc[-1],
            'u_top': layer_df['u'].iloc[0], 'u_bot': layer_df['u'].iloc[-1],
            'ea_top': ea_arr[0], 'ea_bot': ea_arr[-1],
            'ea_soil_top_uncapped': ea_soil_top, 'ea_soil_bot_uncapped': ea_soil_bot,
            'has_tension': has_tension, 'zc': zc, 'Ea': Ea, 'za': za,
            # 被动区特征点 (若无则为0)
            'sigma_p_top': sigma_p_top, 'sigma_p_bot': sigma_p_bot,
            'u_p_top': u_p_top, 'u_p_bot': u_p_bot,
            'ep_top': ep_top, 'ep_bot': ep_bot, 'dz_p': dz_p,
            'Ep': Ep, 'zp': zp,
            # 系数
            'Ka': Ka, 'Kp': Kp
        })
        
        top_z = bot_z
        
    calc_df = pd.DataFrame(results)
    return calc_df, layer_stats