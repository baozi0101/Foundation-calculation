import numpy as np
import pandas as pd
from scipy.optimize import brentq
from utils.materials import get_concrete_params, get_steel_params

def _chunk_latex(terms, items_per_line=2):
    if not terms: return "0"
    lines = [" + ".join(terms[i:i+items_per_line]) for i in range(0, len(terms), items_per_line)]
    result = " \\\\ &\\quad + ".join(lines)
    result = result.replace("+ -", "- ").replace("+  -", "- ")
    return result

class RetainingPile:
    def __init__(self, diameter: float, spacing: float, concrete_grade: str, steel_grade: str, cover: float = 50.0):
        self.d = diameter            
        self.s = spacing             
        self.conc_grade = concrete_grade
        self.steel_grade = steel_grade
        self.cover = cover           

    def calc_internal_forces(self, calc_df: pd.DataFrame, H0: float, hd: float):
        L = H0 + hd
        df = calc_df[calc_df['z'] <= L + 0.01].copy()
        z = df['z'].values
        ea = df['ea'].values
        ep = df['ep'].values

        q_net = ea - ep  
        V = np.zeros_like(z)
        M = np.zeros_like(z)

        for i in range(1, len(z)):
            dz = z[i] - z[i-1]
            q_avg = (q_net[i] + q_net[i-1]) / 2.0
            V[i] = V[i-1] + q_avg * dz
            V_avg = (V[i] + V[i-1]) / 2.0
            M[i] = M[i-1] + V_avg * dz

        crossed_zero = False
        idx_zero = len(z) - 1
        z_zero_shear = z[-1]

        for i in range(1, len(z)):
            if z[i] >= H0 and V[i] <= 0 and V[i-1] > 0:
                crossed_zero = True
                idx_zero = i
                z_zero_shear = z[i]
                break

        if not crossed_zero:
            idx_zero = np.argmax(M)
            z_zero_shear = z[idx_zero]

        M_max = M[idx_zero]
        V_max = np.max(np.abs(V[:idx_zero+1]))

        df['V'] = V
        df['M'] = M

        df_v = df[df['z'] <= H0 + 0.001]
        v_terms = [f"{np.trapz(df_v[df_v['layer_id']==lid]['ea'], df_v[df_v['layer_id']==lid]['z']):.1f}" 
                   for lid in df_v['layer_id'].unique() if np.trapz(df_v[df_v['layer_id']==lid]['ea'], df_v[df_v['layer_id']==lid]['z']) > 0.1]
        v_str = _chunk_latex(v_terms, items_per_line=4)

        df_m = df[df['z'] <= z_zero_shear + 0.001]
        m_terms = []
        for lid in df_m['layer_id'].unique():
            ldf = df_m[df_m['layer_id'] == lid]
            lz = ldf['z'].values
            lEa = np.trapz(ldf['ea'].values, lz)
            lza = np.trapz(lz * ldf['ea'].values, lz) / lEa if lEa > 0 else 0
            lEp = np.trapz(ldf['ep'].values, lz)
            lzp = np.trapz(lz * ldf['ep'].values, lz) / lEp if lEp > 0 else 0

            if lEa > 0.1: m_terms.append(f"{lEa:.1f} \\times {z_zero_shear - lza:.2f}")
            if lEp > 0.1: m_terms.append(f"- {lEp:.1f} \\times {z_zero_shear - lzp:.2f}")
        m_str = _chunk_latex(m_terms, items_per_line=2)

        return df, M_max, V_max, z_zero_shear, v_str, m_str

    def calc_overturning_stability(self, calc_df: pd.DataFrame, H0: float, hd: float):
        L = H0 + hd
        df = calc_df[calc_df['z'] <= L + 0.01].copy()
        z = df['z'].values
        ea = df['ea'].values
        ep = df['ep'].values

        arm = L - z
        M_Ea_tot = np.trapz(ea * arm, z)
        
        mask_pas = z >= H0
        M_Ep_tot = np.trapz(ep[mask_pas] * arm[mask_pas], z[mask_pas]) if np.any(mask_pas) else 0

        ea_terms, ep_terms = [], []
        for lid in df['layer_id'].unique():
            ldf = df[df['layer_id'] == lid]
            lz = ldf['z'].values
            lEa = np.trapz(ldf['ea'].values, lz)
            lza = np.trapz(lz * ldf['ea'].values, lz) / lEa if lEa > 0 else 0
            if lEa > 0.1: ea_terms.append(f"{lEa:.1f} \\times {L - lza:.2f}")

            lEp = np.trapz(ldf['ep'].values, lz)
            lzp = np.trapz(lz * ldf['ep'].values, lz) / lEp if lEp > 0 else 0
            if lEp > 0.1 and np.any(lz >= H0): ep_terms.append(f"{lEp:.1f} \\times {L - lzp:.2f}")

        return {
            'L': L, 'M_Ea': M_Ea_tot, 'M_Ep': M_Ep_tot,
            'K_s': M_Ep_tot / M_Ea_tot if M_Ea_tot > 0 else float('inf'),
            'min_hd': 0.8 * H0, 'is_hd_ok': hd >= 0.8 * H0,
            'ea_str': _chunk_latex(ea_terms, 2), 'ep_str': _chunk_latex(ep_terms, 2)
        }

    def calc_reinforcement(self, M_max_per_meter: float, gamma_0=1.0, gamma_f=1.25):
        M_design = M_max_per_meter * self.s * gamma_0 * gamma_f
        fc_MPa = get_concrete_params(self.conc_grade)['f_c']
        fy_MPa = get_steel_params(self.steel_grade)['f_y']
        
        fc_kpa = fc_MPa * 1000
        fy_kpa = fy_MPa * 1000
        
        r = self.d / 2.0  
        A = np.pi * r**2  
        rs = r - (self.cover + 12.5) / 1000.0  
        
        if M_design <= 0:
            return {'M_design': 0, 'As': 0, 'n_bars': 6, 'bar_dia': 25, 'fy': fy_MPa, 'rs_mm': rs*1000, 'alpha': 0, 'alpha_t': 0}
            
        def equation(alpha):
            alpha_t = 1.25 - 2 * alpha
            if alpha >= 0.625: alpha_t = 0
            if alpha_t - alpha <= 0: return 1e9 
            term1 = alpha * fc_kpa * A * (1 - np.sin(2 * np.pi * alpha) / (2 * np.pi * alpha))
            As = term1 / ((alpha_t - alpha) * fy_kpa)
            M_calc = (2/3) * fc_kpa * A * r * (np.sin(np.pi * alpha)**3) / np.pi + \
                     fy_kpa * As * rs * (np.sin(np.pi * alpha) + np.sin(np.pi * alpha_t)) / np.pi
            return M_calc - M_design

        try:
            alpha = brentq(equation, 1e-5, 0.416)
            alpha_t = 1.25 - 2 * alpha
            if alpha >= 0.625: alpha_t = 0
            term1 = alpha * fc_kpa * A * (1 - np.sin(2 * np.pi * alpha) / (2 * np.pi * alpha))
            As_m2 = term1 / ((alpha_t - alpha) * fy_kpa)
            As_mm2 = As_m2 * 1e6
        except Exception as e:
            alpha = 0; alpha_t = 0
            As_mm2 = (M_design * 1e6) / (0.85 * fy_MPa * (rs * 1000) * 2.0)
            
        n_bars = max(int(np.ceil(As_mm2 / (np.pi * (25/2)**2))), 6)
        if n_bars % 2 != 0: n_bars += 1
            
        return {'M_design': M_design, 'As': As_mm2, 'n_bars': n_bars, 'bar_dia': 25, 'fy': fy_MPa, 'rs_mm': rs*1000, 'alpha': alpha, 'alpha_t': alpha_t}

    def calc_shear_reinforcement(self, V_max_per_meter: float, gamma_0=1.0, gamma_f=1.25):
        V_design = V_max_per_meter * self.s * gamma_0 * gamma_f
        fc = get_concrete_params(self.conc_grade)['f_c']
        ft = get_concrete_params(self.conc_grade)['f_t']
        fyv = 210 if self.steel_grade == "HPB300" else 300 
        
        b = self.d * 1000 * 0.8 
        h0 = self.d * 1000 - self.cover - 12.5 
        beta_c = 1.0 
        V_max_limit = 0.25 * beta_c * fc * b * h0 / 1000 
        h0_beta = max(min(h0, 2000), 800)
        beta_h = (800 / h0_beta)**0.25
        V_c = 0.7 * beta_h * ft * b * h0 / 1000 
        
        req_Asv_s = 0.0 if V_design <= V_c else (V_design - V_c) * 1000 / (fyv * h0)
        s_spacing = (3.14159 * 4**2 * 2) / req_Asv_s if req_Asv_s > 0 else 200
        s_spacing = min(max(int(s_spacing / 10) * 10, 100), 200) 
        
        return {'V_design': V_design, 'V_max_limit': V_max_limit, 'beta_c': beta_c, 'beta_h': beta_h, 'V_c': V_c, 'req_Asv_s': req_Asv_s, 'stirrup': f"Φ8 @ {s_spacing}", 'ft': ft, 'fc': fc, 'b': b, 'h0': h0, 'fyv': fyv}

    def calc_capping_beam(self):
        b = self.d * 1000 + 100 
        h = max(400, int(0.6 * self.d * 1000)) 
        As_min = b * h * 0.0015
        n_bars = max(4, int(np.ceil(As_min / (3.14159 * 8**2))))
        return {'b': b, 'h': h, 'As_min': As_min, 'n_bars': n_bars, 'bar_dia': 16}

    def calc_settlement(self, H0: float, hd: float, layer_stats: list):
        L = H0 + hd
        phi_sum, h_sum = 0, 0
        for stat in layer_stats:
            dz = max(0, min(stat['bot'], L) - min(stat['top'], L))
            phi_sum += stat['phi'] * dz
            h_sum += dz
        phi_avg = phi_sum / h_sum if h_sum > 0 else 20.0
        
        x0 = L * np.tan(np.pi/4 - np.radians(phi_avg)/2)
        v_max = 0.002 * H0 
        Sw_mm2 = 0.5 * v_max * L * 1e6
        delta_max_tri = 2 * Sw_mm2 / (x0 * 1000)
        delta_max_para = 3 * Sw_mm2 / (x0 * 1000)
        
        x_set = np.linspace(0, x0, 50)
        y_tri = delta_max_tri * (1 - x_set/x0)
        y_para = delta_max_para * (1 - x_set/x0)**2
        
        return {'phi_avg': phi_avg, 'x0': x0, 'v_max_mm': v_max * 1000, 'Sw_mm2': Sw_mm2, 'delta_max_tri': delta_max_tri, 'delta_max_para': delta_max_para, 'x_set': x_set, 'y_tri': y_tri, 'y_para': y_para}

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
        """【升级版】：采用网格搜索 (Grid Search) 自动寻找最危险的滑裂面圆心位置"""
        L = H0 + hd
        
        # 建立圆心搜索网格
        # Xc: 位于坑外地表，0.1H0 ~ 1.0H0
        # Zc: 位于坑顶之上，-H0 ~ -0.1H0
        xc_grid = np.linspace(0.1 * H0, 1.0 * H0, 10)
        zc_grid = np.linspace(-H0, -0.1 * H0, 10)
        
        min_Ks = float('inf')
        best_result = None
        
        for x_c in xc_grid:
            for z_c in zc_grid:
                # 假定最危险滑动面穿过桩底 (0, L)
                R = np.sqrt(x_c**2 + (L - z_c)**2)
                
                # 计算圆弧与坑底及地表的交点
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
                        is_valid = False
                        break
                    
                    z_arc = z_c + np.sqrt(val_mid)
                    z_surf = 0 if x_mid > 0 else H0
                    h_slice = z_arc - z_surf
                    
                    if h_slice <= 0: continue
                    
                    # 倾角 theta
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
                        '编号': i + 1,
                        'x_mid (m)': round(x_mid, 2),
                        '厚度 h (m)': round(h_slice, 2),
                        '倾角 θ (°)': round(np.degrees(theta_rad), 1),
                        '弧长 l (m)': round(l_arc, 2),
                        'c (kPa)': c,
                        'φ (°)': phi,
                        '自重+超载 (kN/m)': round(W_j, 1),
                        '抗滑力 (kN/m)': round(res_j, 1),
                        '下滑力 (kN/m)': round(drv_j, 1)
                    })
                    
                if not is_valid or M_drive <= 0: continue
                
                Ks = M_resist / M_drive
                
                # 如果找到更小的安全系数，则更新最优结果
                if Ks < min_Ks:
                    min_Ks = Ks
                    plot_angles = np.linspace(0, 2*np.pi, 100)
                    x_plot = x_c + R * np.sin(plot_angles)
                    z_plot = z_c + R * np.cos(plot_angles)
                    
                    best_result = {
                        'xc': x_c, 'zc': z_c, 'R': R, 'Ks': Ks,
                        'M_resist': M_resist/R, 'M_drive': M_drive/R,
                        'x_plot': x_plot, 'z_plot': z_plot,
                        'slices_data': slices_data, 'b_slice': b_slice
                    }
                    
        return best_result or {'xc': 0, 'zc': 0, 'R': L, 'Ks': 999.0, 'M_resist': 0, 'M_drive': 0, 'x_plot': np.array([]), 'z_plot': np.array([]), 'slices_data': [], 'b_slice': 0}