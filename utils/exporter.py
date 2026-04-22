import io
import pandas as pd
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

def generate_docxtpl_report(template_path: str, context: dict, df_table: pd.DataFrame, fig=None):
    """
    基于 docxtpl 的高级 Word 计算书生成引擎
    :param template_path: 本地 Word 模板文件的相对路径
    :param context: 基础变量字典，包含要填入模板的数据
    :param df_table: 需要渲染进表格的 Pandas DataFrame (供土钉墙等模块使用)
    :param fig: Plotly 图表对象
    """
    # 1. 加载模板
    doc = DocxTemplate(template_path)
    
    # 2. 处理表格数据 (将 DataFrame 转换为字典列表供 jinja2 循环)
    nail_table_data = []
    if not df_table.empty:
        for idx, row in df_table.iterrows():
            nail_table_data.append({
                'layer_id': row.get('层号', '-'),
                'depth': f"{row.get('深度 z (m)', 0):.2f}" if isinstance(row.get('深度 z (m)'), (int, float)) else "-",
                'length': f"{row.get('长度 L (m)', 0):.2f}" if isinstance(row.get('长度 L (m)'), (int, float)) else "-",
                'force': f"{row.get('拉力 Nk (kN)', 0):.2f}" if isinstance(row.get('拉力 Nk (kN)'), (int, float)) else "-",
                'res_force': f"{row.get('抗拔 Rk (kN)', 0):.2f}" if isinstance(row.get('抗拔 Rk (kN)'), (int, float)) else "-",
                'kt': f"{row.get('Kt', 0):.2f}" if isinstance(row.get('Kt'), (int, float)) else "-"
            })
    
    # 将表格数据加入上下文中
    context['nail_table'] = nail_table_data
    
    # 3. 处理图表图片
    if fig:
        # 渲染高清 PNG 到内存
        img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
        img_stream = io.BytesIO(img_bytes)
        
        # 转换为 docxtpl 支持的 InlineImage 对象，设置宽度为 160 毫米
        context['plot_image'] = InlineImage(doc, img_stream, width=Mm(160))
    else:
        context['plot_image'] = "（未生成图表）"

    # 4. 核心渲染步骤：用 context 字典替换模板中的所有占位符
    doc.render(context)
    
    # 5. 保存到内存并返回
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer