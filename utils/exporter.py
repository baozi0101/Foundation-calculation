import io
import pandas as pd
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

def generate_docxtpl_report(template_path: str, context: dict, df_table: pd.DataFrame = None, fig=None, tables: dict = None, figs: dict = None):
    """
    基于 docxtpl 的高级 Word 计算书生成引擎 (兼容单图单表与多图多表)
    """
    doc = DocxTemplate(template_path)
    
    # 1. 兼容旧版：处理单表格数据 (供土钉墙使用)
    if df_table is not None and not df_table.empty:
        nail_table_data = []
        for idx, row in df_table.iterrows():
            nail_table_data.append({
                'layer_id': row.get('层号', '-'),
                'depth': f"{row.get('深度 z (m)', 0):.2f}" if isinstance(row.get('深度 z (m)'), (int, float)) else "-",
                'length': f"{row.get('长度 L (m)', 0):.2f}" if isinstance(row.get('长度 L (m)'), (int, float)) else "-",
                'force': f"{row.get('拉力 Nk (kN)', 0):.2f}" if isinstance(row.get('拉力 Nk (kN)', 0), (int, float)) else "-",
                'res_force': f"{row.get('抗拔 Rk (kN)', 0):.2f}" if isinstance(row.get('抗拔 Rk (kN)'), (int, float)) else "-",
                'kt': f"{row.get('Kt', 0):.2f}" if isinstance(row.get('Kt'), (int, float)) else "-"
            })
        context['nail_table'] = nail_table_data
    
    # 2. 兼容旧版：处理单图表图片
    if fig is not None:
        try:
            img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
            img_stream = io.BytesIO(img_bytes)
            context['plot_image'] = InlineImage(doc, img_stream, width=Mm(160))
        except Exception as e:
            context['plot_image'] = f"[⚠️ 图片生成失败: {str(e).splitlines()[0]}]"

    # 3. 新版增强：处理多表格字典 (供悬臂排桩的条分法表格使用)
    if tables:
        for tag, df in tables.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                context[tag] = df.to_dict('records')

    # 4. 新版增强：处理多图表字典 (供悬臂排桩的 3 幅图使用)
    if figs:
        for tag, curr_fig in figs.items():
            try:
                img_bytes = curr_fig.to_image(format="png", width=800, height=600, scale=2)
                img_stream = io.BytesIO(img_bytes)
                context[tag] = InlineImage(doc, img_stream, width=Mm(160))
            except Exception as e:
                context[tag] = f"[⚠️ 图片生成失败: {str(e).splitlines()[0]}]"

    # 5. 核心渲染步骤
    doc.render(context)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return buffer