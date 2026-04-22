import numpy as np
import pandas as pd

class SoilNailWall:
    def __init__(self, Sx: float, Sz: float, alpha: float, d_hole: float, fyk: float, f_c: float, fc_grade: str):
        self.Sx = Sx              # 水平间距 (m)
        self.Sz = Sz              # 竖向间距 (m)
        self.alpha = alpha        # 土钉倾角 (°)
        self.d_hole = d_hole      # 成孔直径 (m)
        self.fyk = fyk            # 钢筋抗拉强度标准值 (MPa)
        self.f_c = f_c            # 混凝土轴心抗压强度设计值 (MPa)
        self.fc_grade = fc_grade

    def calc_nail_forces(self, calc_df: pd.DataFrame, H0: float, nail_depths: list, nail_lengths: list, layer_stats: list, df_soil: pd.DataFrame):
        """计算每层土钉的轴向拉力 Nk 与极限抗拔承载力 Rk (分段积分)"""
        alpha_rad = np.radians(self.alpha)
        results = []
        
        # 寻找基坑底以上土层的加权内摩擦角 phi_m
        phi_sum, h_sum = 0, 0
        for stat in layer_stats:
            dz = max(0, min(stat['bot'], H0) - min(stat['top'], 0))
            phi_sum += stat['phi'] * dz
            h_sum += dz
        phi_m = phi_sum / h_sum if h_sum > 0 else 20.0
        
        # 破裂面倾角 (假设破裂面过坡脚)
        theta_crack = np.radians(45 + phi_m / 2)
        
        for i, z_j in enumerate(nail_depths):
            L_j = nail_lengths[i]
            
            # 1. 提取该深度的土压力 p_akj
            df_z = calc_df.iloc[(calc_df['z'] - z_j).abs().argsort()[:1]]
            p_akj = df_z['ea'].values[0]
            
            # 2. 计算土钉轴向拉力标准值 N_kj
            N_kj = (1.0 / np.cos(alpha_rad)) * 1.0 * 1.0 * p_akj * self.Sx * self.Sz
            
            # 3. 计算破裂面位置
            x_crack = (H0 - z_j) / np.tan(theta_crack)
            Lx_nail = L_j * np.cos(alpha_rad)
            L_out_x = max(0, Lx_nail - x_crack)
            L_out_total = L_out_x / np.cos(alpha_rad)
            
            # 如果土钉完全在破裂面内，抗拔力为0
            if L_out_total <= 0:
                results.append({
                    '层号': i+1, '深度 z (m)': z_j, '长度 L (m)': L_j,
                    'ea (kPa)': round(p_akj, 1), '拉力 Nk (kN)': round(N_kj, 1),
                    '有效长 Lout (m)': 0.0, '抗拔 Rk (kN)': 0.0, 'Kt': 0.0,
                    '分段详情': "土钉未能穿透破裂面"
                })
                continue
                
            # 4. 精确分段计算抗拔力 R_kj = pi * d * sum(qsik * li)
            R_kj = 0.0
            l_out_start = L_j - L_out_total # 有效锚固段起点的锚杆长度坐标
            l_out_end = L_j                 # 有效锚固段终点的锚杆长度坐标
            
            segments_info = [] # 记录分段信息用于界面展示
            
            z_cum = 0.0
            for _, r in df_soil.iterrows():
                h_layer = r['厚度(m)']
                z_top = z_cum
                z_bot = z_cum + h_layer
                z_cum += h_layer
                
                qsik = r.get('极限粘结强度(kPa)', 40.0)
                
                # 计算土钉穿过该土层的起始和终止长度坐标
                # z = z_j + l * sin(alpha) => l = (z - z_j) / sin(alpha)
                l_layer_start = (z_top - z_j) / np.sin(alpha_rad) if self.alpha > 0 else 0
                l_layer_end = (z_bot - z_j) / np.sin(alpha_rad) if self.alpha > 0 else (L_j if z_top <= z_j <= z_bot else 0)
                
                # 寻找土钉该土层段 与 有效锚固段 的交集
                l_intersect_start = max(l_out_start, l_layer_start)
                l_intersect_end = min(l_out_end, l_layer_end)
                
                l_i = max(0, l_intersect_end - l_intersect_start)
                
                if l_i > 0:
                    R_kj += np.pi * self.d_hole * qsik * l_i
                    segments_info.append(f"{qsik:.0f}×{l_i:.2f}m")
            
            # 如果土钉超深(超过所有输入土层)，取最后一层土参数计算剩余长度
            if z_j + l_out_end * np.sin(alpha_rad) > z_cum:
                l_extra = l_out_end - max(l_out_start, (z_cum - z_j)/np.sin(alpha_rad) if self.alpha > 0 else l_out_start)
                if l_extra > 0:
                    qsik_last = df_soil.iloc[-1].get('极限粘结强度(kPa)', 40.0)
                    R_kj += np.pi * self.d_hole * qsik_last * l_extra
                    segments_info.append(f"{qsik_last:.0f}×{l_extra:.2f}m(超深)")
            
            Kt = R_kj / N_kj if N_kj > 0 else float('inf')
            
            results.append({
                '层号': i+1, '深度 z (m)': z_j, '长度 L (m)': L_j,
                'ea (kPa)': round(p_akj, 1), '拉力 Nk (kN)': round(N_kj, 1),
                '有效长 Lout (m)': round(L_out_total, 2), 
                '抗拔 Rk (kN)': round(R_kj, 1), 'Kt': round(Kt, 2),
                '分段详情': " + ".join(segments_info)
            })
            
        return pd.DataFrame(results), phi_m

    def calc_facing_design(self, N_kj_max: float, thickness: float = 0.1):
        """面层单向板配筋计算"""
        p = 1.25 * (N_kj_max / (self.Sx * self.Sz)) 
        L0 = min(self.Sx, self.Sz)
        M = (1.0 / 8.0) * p * L0**2 
        
        b = 1000.0 
        h = thickness * 1000
        h0 = h - 20 
        
        alpha_1 = 1.0
        fc_mpa = self.f_c
        fy_mpa = self.fyk
        
        alpha_s = (M * 1e6) / (alpha_1 * fc_mpa * b * h0**2)
        xi = 1 - np.sqrt(1 - 2 * alpha_s) if alpha_s <= 0.5 else 0.5
        As = (xi * alpha_1 * fc_mpa * b * h0) / fy_mpa
        
        ft = 1.43 
        rho_min = max(0.002, 0.45 * ft / fy_mpa)
        As_min = rho_min * b * h
        As_final = max(As, As_min)
        
        return {'p': p, 'M': M, 'alpha_s': alpha_s, 'As': As_final, 'As_min': As_min}

    def calc_global_stability(self, H0: float, q: float, layer_stats: list, nail_df: pd.DataFrame):
        """采用网格寻优，引入土钉附加抗力的瑞典条分法"""
        xc_grid = np.linspace(0.1 * H0, 1.0 * H0, 10)
        zc_grid = np.linspace(-H0, -0.1 * H0, 10)
        
        min_Ks = float('inf')
        best_result = None
        alpha_rad = np.radians(self.alpha)
        
        for x_c in xc_grid:
            for z_c in zc_grid:
                R = np.sqrt(x_c**2 + (H0 - z_c)**2)
                val_left = R**2 - (H0 - z_c)**2
                val_right = R**2 - (0 - z_c)**2
                if val_left < 0 or val_right < 0: continue
                
                x_left = x_c - np.sqrt(val_left)
                x_right = x_c + np.sqrt(val_right)
                if x_left >= x_right: continue
                
                N_slices = 20
                b_slice = (x_right - x_left) / N_slices
                M_drive, M_resist_soil = 0, 0
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
                    
                    M_resist_soil += res_j * R
                    M_drive += drv_j * R
                    
                    slices_data.append({
                        '编号': i + 1, 'x_mid (m)': round(x_mid, 2), '厚度 h (m)': round(h_slice, 2),
                        '倾角 θ (°)': round(np.degrees(theta_rad), 1), '弧长 l (m)': round(l_arc, 2),
                        'c (kPa)': c, 'φ (°)': phi, '自重+超载 (kN/m)': round(W_j, 1),
                        '抗滑力 (kN/m)': round(res_j, 1), '下滑力 (kN/m)': round(drv_j, 1)
                    })

                if not is_valid or M_drive <= 0: continue

                M_nail_resist = 0
                for _, nail in nail_df.iterrows():
                    z_j = nail['深度 z (m)']
                    Rk = nail['抗拔 Rk (kN)']
                    y_diff = z_j - z_c
                    if abs(y_diff) > R: continue
                    
                    x_intersect = x_c - np.sqrt(R**2 - y_diff**2)
                    if x_intersect > 0: continue 
                    
                    theta_k_rad = np.arcsin(np.clip((x_intersect - x_c) / R, -1.0, 1.0))
                    slice_layer = next((s for s in layer_stats if s['top'] <= z_j <= s['bot']), layer_stats[-1])
                    phi_k = slice_layer['phi']
                    psi_v = 0.5 * np.sin(theta_k_rad + alpha_rad) * np.tan(np.radians(phi_k))
                    
                    delta_M = (Rk / self.Sx) * (np.cos(theta_k_rad + alpha_rad) + psi_v) * R
                    M_nail_resist += max(0, delta_M)

                M_resist_total = M_resist_soil + M_nail_resist
                Ks = M_resist_total / M_drive
                
                if Ks < min_Ks:
                    min_Ks = Ks
                    plot_angles = np.linspace(0, 2*np.pi, 100)
                    best_result = {
                        'xc': x_c, 'zc': z_c, 'R': R, 'Ks': Ks,
                        'M_resist_soil': M_resist_soil/R, 'M_resist_nail': M_nail_resist/R, 
                        'M_drive': M_drive/R,
                        'x_plot': x_c + R * np.sin(plot_angles), 'z_plot': z_c + R * np.cos(plot_angles),
                        'slices_data': slices_data, 'b_slice': b_slice
                    }

        return best_result or {'xc': 0, 'zc': 0, 'R': H0, 'Ks': 999.0, 'M_resist_soil': 0, 'M_resist_nail': 0, 'M_drive': 0, 'x_plot': np.array([]), 'z_plot': np.array([]), 'slices_data': [], 'b_slice': 0}