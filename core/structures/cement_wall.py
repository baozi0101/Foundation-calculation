import numpy as np
import pandas as pd

class CementSoilWall:
    def __init__(self, b: float, f_cs: float, gamma_cs: float = 19.0):
        self.b = b             # 水泥土墙厚度/宽度 (m)
        self.f_cs = f_cs       # 水泥土轴心抗压强度设计值 (kPa)
        self.gamma_cs = gamma_cs # 水泥土平均重度 (kN/m³)

    # <--- 【修改点】：传参由 zw 变为 zw_out 和 zw_in
    def calc_stability(self, calc_df: pd.DataFrame, H0: float, hd: float, zw_out: float, zw_in: float, layer_stats: list):
        """计算整体抗倾覆 (Kov) 和抗滑移 (Ksl) 稳定性"""
        L = H0 + hd
        df = calc_df[calc_df['z'] <= L + 0.01].copy()
        z = df['z'].values
        ea = df['ea'].values
        ep = df['ep'].values

        # 积分求合力与作用点
        dz = np.diff(z)
        ea_avg = (ea[:-1] + ea[1:]) / 2.0
        ep_avg = (ep[:-1] + ep[1:]) / 2.0
        z_avg = (z[:-1] + z[1:]) / 2.0

        Eak = np.sum(ea_avg * dz)
        Epk = np.sum(ep_avg * dz)

        aa = np.sum(ea_avg * dz * (L - z_avg)) / Eak if Eak > 0 else 0
        ap = np.sum(ep_avg * dz * (L - z_avg)) / Epk if Epk > 0 else 0

        # 自重 G 及作用点 (矩形截面)
        G = self.gamma_cs * self.b * L
        aG = self.b / 2.0

        # 墙底水压力 um (按规范取内外水位平均值)
        hwa = max(0, L - zw_out)             # <--- 【修改点】：坑外水头，从坑外水位算起
        hwp = max(0, L - (H0 + zw_in))       # <--- 【修改点】：坑内水头，从坑底+坑内水位算起
        um = 10.0 * (hwa + hwp) / 2.0 if (hwa > 0 or hwp > 0) else 0.0

        # 获取基底土层参数
        bot_layer = next((s for s in layer_stats if s['top'] <= L <= s['bot']), layer_stats[-1])
        c, phi = bot_layer['c'], bot_layer['phi']

        # 抗倾覆安全系数 Kov
        M_res_ov = Epk * ap + (G - um * self.b) * aG
        M_drv_ov = Eak * aa
        Kov = M_res_ov / M_drv_ov if M_drv_ov > 0 else float('inf')

        # 抗滑移安全系数 Ksl
        F_res_sl = Epk + (G - um * self.b) * np.tan(np.radians(phi)) + c * self.b
        F_drv_sl = Eak
        Ksl = F_res_sl / F_drv_sl if F_drv_sl > 0 else float('inf')

        return {
            'Eak': Eak, 'Epk': Epk, 'aa': aa, 'ap': ap,
            'G': G, 'um': um, 'Kov': Kov, 'Ksl': Ksl,
            'M_res_ov': M_res_ov, 'M_drv_ov': M_drv_ov,
            'F_res_sl': F_res_sl, 'F_drv_sl': F_drv_sl,
            'c': c, 'phi': phi
        }

    def calc_section_stress(self, calc_df: pd.DataFrame, H0: float, hd: float, gamma0: float, gammaF: float = 1.25):
        """水泥土墙正截面(压、拉)及斜截面(剪)承载力验算"""
        L = H0 + hd
        df = calc_df[calc_df['z'] <= L + 0.01].copy()
        z = df['z'].values
        ea = df['ea'].values
        ep = df['ep'].values

        q_net = ea - ep  
        V = np.zeros_like(z)
        M = np.zeros_like(z)

        # 累加求剪力与弯矩分布
        for i in range(1, len(z)):
            dz = z[i] - z[i-1]
            q_avg = (q_net[i] + q_net[i-1]) / 2.0
            V[i] = V[i-1] + q_avg * dz
            V_avg = (V[i] + V[i-1]) / 2.0
            M[i] = M[i-1] + V_avg * dz

        df['V'] = V
        df['M'] = M

        # 寻找最大弯矩处 (用于拉压应力验算)
        idx_M = np.argmax(M)
        Mk_max = M[idx_M]
        z_M = z[idx_M]
        
        # 寻找最大剪力处 (用于剪应力验算)
        idx_V = np.argmax(np.abs(V))
        Vk_max = np.abs(V[idx_V])
        z_V = z[idx_V]

        # 设计值
        Mi = gamma0 * gammaF * Mk_max
        Vi = gamma0 * gammaF * Vk_max
        
        # 1. 压应力与拉应力验算 (在最大弯矩截面 z_M 处)
        sigma_c = gamma0 * gammaF * self.gamma_cs * z_M + (6 * Mi) / (self.b**2)
        sigma_t = (6 * Mi) / (self.b**2) - self.gamma_cs * z_M
        
        # 2. 剪应力验算 (在最大剪力截面 z_V 处)
        Gi = self.gamma_cs * self.b * z_V # 验算截面以上墙体自重
        mu = 0.45 # 墙体抗剪断系数取 0.4~0.5 之间
        tau = (Vi - mu * Gi) / self.b if (Vi - mu * Gi) > 0 else 0.0

        return {
            'df': df, 'z_M': z_M, 'Mk_max': Mk_max, 'Mi': Mi,
            'z_V': z_V, 'Vk_max': Vk_max, 'Vi': Vi,
            'sigma_c': sigma_c, 'sigma_t': sigma_t, 'tau': tau,
            'Gi': Gi, 'mu': mu
        }

    def calc_heave_stability(self, H0: float, hd: float, q: float, layer_stats: list):
        L = H0 + hd
        bot_layer = next((s for s in layer_stats if s['top'] <= L <= s['bot']), layer_stats[-1])
        c, phi = bot_layer['c'], bot_layer['phi']
        gamma_bot = bot_layer['gamma_sat'] if bot_layer['mode'] == '水土合算' else bot_layer['gamma_nat']
        gamma_top_avg = 19.5 
        
        if phi > 0:
            Nq = np.exp(np.pi * np.tan(np.radians(phi))) * np.tan(np.radians(45 + phi/2))**2
            Nc = (Nq - 1) / np.tan(np.radians(phi))
        else:
            Nq, Nc = 1.0, 5.14
            
        p_res = gamma_bot * hd * Nq + c * Nc
        p_act = gamma_top_avg * L + q
        Kl = p_res / p_act if p_act > 0 else float('inf')
        return {'c': c, 'phi': phi, 'Nq': Nq, 'Nc': Nc, 'p_res': p_res, 'p_act': p_act, 'Kl': Kl, 'gamma_bot': gamma_bot, 'gamma_top_avg': gamma_top_avg}

    def calc_global_stability(self, H0: float, hd: float, q: float, layer_stats: list):
        """采用网格搜索 (Grid Search) 自动寻找最危险的滑裂面圆心位置"""
        L = H0 + hd
        
        xc_grid = np.linspace(0.1 * H0, 1.0 * H0, 10)
        zc_grid = np.linspace(-H0, -0.1 * H0, 10)
        
        min_Ks = float('inf')
        best_result = None
        
        for x_c in xc_grid:
            for z_c in zc_grid:
                R = np.sqrt(x_c**2 + (L - z_c)**2)
                val_left = R**2 - (H0 - z_c)**2
                val_right = R**2 - (0 - z_c)**2
                
                if val_left < 0 or val_right < 0: continue
                
                x_left = x_c - np.sqrt(val_left)
                x_right = x_c + np.sqrt(val_right)
                if x_left >= x_right: continue
                
                N_slices = 20
                b_slice = (x_right - x_left) / N_slices
                M_drive, M_resist = 0, 0
                slices_data = []
                is_valid = True
                
                for i in range(N_slices):
                    x_mid = x_left + (i + 0.5) * b_slice
                    val_mid = R**2 - (x_mid - x_c)**2
                    if val_mid < 0: 
                        is_valid = False; break
                    
                    z_arc = z_c + np.sqrt(val_mid)
                    z_surf = 0 if x_mid > 0 else H0
                    h_slice = z_arc - z_surf
                    if h_slice <= 0: continue
                    
                    theta_rad = np.arcsin(np.clip((x_mid - x_c) / R, -1.0, 1.0))
                    l_arc = b_slice / np.cos(theta_rad)
                    
                    z_mid = (z_surf + z_arc) / 2.0
                    slice_layer = next((s for s in layer_stats if s['top'] <= z_mid <= s['bot']), layer_stats[-1])
                    c, phi = slice_layer['c'], slice_layer['phi']
                    gamma = slice_layer['gamma_sat']
                    
                    delta_G = h_slice * b_slice * gamma
                    q_j = q if x_mid > 0 else 0
                    W_j = delta_G + q_j * b_slice
                    
                    res_j = c * l_arc + W_j * np.cos(theta_rad) * np.tan(np.radians(phi))
                    drv_j = W_j * np.sin(theta_rad)
                    
                    M_resist += res_j * R
                    M_drive += drv_j * R
                    
                    slices_data.append({
                        '编号': i + 1, 'x_mid (m)': round(x_mid, 2), '厚度 h (m)': round(h_slice, 2),
                        '倾角 θ (°)': round(np.degrees(theta_rad), 1), '弧长 l (m)': round(l_arc, 2),
                        'c (kPa)': c, 'φ (°)': phi, '自重+超载 (kN/m)': round(W_j, 1),
                        '抗滑力 (kN/m)': round(res_j, 1), '下滑力 (kN/m)': round(drv_j, 1)
                    })
                    
                if not is_valid or M_drive <= 0: continue
                Ks = M_resist / M_drive
                
                if Ks < min_Ks:
                    min_Ks = Ks
                    plot_angles = np.linspace(0, 2*np.pi, 100)
                    best_result = {
                        'xc': x_c, 'zc': z_c, 'R': R, 'Ks': Ks,
                        'M_resist': M_resist/R, 'M_drive': M_drive/R,
                        'x_plot': x_c + R * np.sin(plot_angles), 'z_plot': z_c + R * np.cos(plot_angles),
                        'slices_data': slices_data, 'b_slice': b_slice
                    }
                    
        return best_result or {'xc': 0, 'zc': 0, 'R': L, 'Ks': 999.0, 'M_resist': 0, 'M_drive': 0, 'x_plot': np.array([]), 'z_plot': np.array([]), 'slices_data': [], 'b_slice': 0}