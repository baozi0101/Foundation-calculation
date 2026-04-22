"""
材料参数库 (Materials Library)
包含混凝土强度设计值、钢筋强度设计值及弹性模量。
数据参考：GB 50010-2010 (2015年版)
"""

# 1. 混凝土强度设计值 (单位: N/mm²)
# f_c: 轴心抗压强度设计值, f_t: 轴心抗拉强度设计值
CONCRETE_PROPERTIES = {
    "C20": {"f_c": 9.6, "f_t": 1.10, "E_c": 2.55e4},
    "C25": {"f_c": 11.9, "f_t": 1.27, "E_c": 2.80e4},
    "C30": {"f_c": 14.3, "f_t": 1.43, "E_c": 3.00e4},
    "C35": {"f_c": 16.7, "f_t": 1.57, "E_c": 3.15e4},
    "C40": {"f_c": 19.1, "f_t": 1.71, "E_c": 3.25e4},
    "C45": {"f_c": 21.1, "f_t": 1.80, "E_c": 3.35e4},
    "C50": {"f_c": 23.1, "f_t": 1.89, "E_c": 3.45e4},
}

# 2. 钢筋强度设计值 (单位: N/mm²)
# f_y: 抗拉强度设计值, f_yv: 箍筋抗拉强度设计值
STEEL_PROPERTIES = {
    "HPB300": {"f_y": 270, "f_yv": 210, "E_s": 2.1e5},
    "HRB400": {"f_y": 360, "f_yv": 300, "E_s": 2.0e5},
    "HRB500": {"f_y": 435, "f_yv": 360, "E_s": 2.0e5},
}

def get_concrete_params(grade: str):
    """获取指定等级混凝土的参数"""
    return CONCRETE_PROPERTIES.get(grade, CONCRETE_PROPERTIES["C30"])

def get_steel_params(grade: str):
    """获取指定等级钢筋的参数"""
    return STEEL_PROPERTIES.get(grade, STEEL_PROPERTIES["HRB400"])