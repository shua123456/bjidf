# -*- coding: utf-8 -*-

import sys
import arcpy
import os
import codecs

reload(sys)
sys.setdefaultencoding('utf-8')

arcpy.env.overwriteOutput = True

# ==============================
# 输出位置
# ==============================

out_folder = r"D:\SRT_ArcPy_Result"

if not os.path.exists(out_folder):
    os.makedirs(out_folder)

out_txt = os.path.join(out_folder, "landuse_area_summary.txt")

# ==============================
# 需要统计的图层
# 名称必须尽量和 ArcMap 左侧图层一致
# 我把“生态绿地/林地”和“生态基地/林地”都放进去了，防止名称不一致
# ==============================

target_layers = [
    u"基地边界",
    u"农业生产用地",
    u"科研试验用地",
    u"设施农业用地",
    u"建设服务用地",
    u"生态绿地/林地",
    u"生态基地/林地",
    u"道路交通用地",
    u"水域水源用地"
]

# ==============================
# 读取当前 ArcMap 工程
# ==============================

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

all_layers = []
found_layers = []
result = []

print u"开始识别当前 ArcMap 中的要素图层……"

for lyr in arcpy.mapping.ListLayers(mxd, "", df):
    if lyr.isFeatureLayer:
        all_layers.append(lyr.name)

print u"当前 ArcMap 中的要素图层如下："
for name in all_layers:
    print u" - " + name

print u""
print u"开始统计目标图层……"

# ==============================
# 面积统计
# ==============================

for lyr in arcpy.mapping.ListLayers(mxd, "", df):

    if not lyr.isFeatureLayer:
        continue

    layer_name = lyr.name

    if layer_name not in target_layers:
        continue

    found_layers.append(layer_name)

    print u"正在处理图层：" + layer_name

    try:
        fc = lyr.dataSource
        desc = arcpy.Describe(fc)
        shape_type = desc.shapeType

        count = 0
        total_area_m2 = 0.0

        if shape_type == "Polygon":

            with arcpy.da.SearchCursor(fc, ["SHAPE@AREA"]) as cursor:
                for row in cursor:
                    count += 1
                    if row[0] is not None:
                        total_area_m2 += row[0]

            total_area_mu = total_area_m2 / 666.6667

            result.append([
                layer_name,
                shape_type,
                count,
                total_area_m2,
                total_area_mu,
                u"成功"
            ])

        else:

            with arcpy.da.SearchCursor(fc, ["OID@"]) as cursor:
                for row in cursor:
                    count += 1

            result.append([
                layer_name,
                shape_type,
                count,
                None,
                None,
                u"非面图层，仅统计数量"
            ])

    except Exception as e:

        result.append([
            layer_name,
            u"未知",
            0,
            None,
            None,
            u"失败：" + unicode(e)
        ])

        print u"处理失败：" + layer_name
        print unicode(e)

# ==============================
# 计算基地总面积
# ==============================

base_area_m2 = None

for row in result:
    if row[0] == u"基地边界" and row[3] is not None:
        base_area_m2 = row[3]

# ==============================
# 输出结果
# ==============================

with codecs.open(out_txt, "w", "utf-8") as f:

    f.write(u"白马基地土地利用面积统计结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、当前 ArcMap 中识别到的要素图层\n")
    for name in all_layers:
        f.write(u"- " + name + u"\n")

    f.write(u"\n二、本次成功匹配到的目标图层\n")
    for name in found_layers:
        f.write(u"- " + name + u"\n")

    f.write(u"\n三、面积统计结果\n")
    f.write(u"图层名称\t几何类型\t要素数量\t总面积_平方米\t总面积_亩\t占基地总面积比例\t状态\n")

    for row in result:

        layer_name = row[0]
        shape_type = row[1]
        count = row[2]
        area_m2 = row[3]
        area_mu = row[4]
        status = row[5]

        if area_m2 is None:

            f.write(u"{}\t{}\t{}\t\t\t\t{}\n".format(
                layer_name,
                shape_type,
                count,
                status
            ))

        else:

            if base_area_m2 is not None and base_area_m2 > 0 and layer_name != u"基地边界":
                ratio = area_m2 / base_area_m2 * 100
                ratio_text = u"{:.2f}%".format(ratio)
            elif layer_name == u"基地边界":
                ratio_text = u"100.00%"
            else:
                ratio_text = u""

            f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\t{}\t{}\n".format(
                layer_name,
                shape_type,
                count,
                area_m2,
                area_mu,
                ratio_text,
                status
            ))

    f.write(u"\n四、说明\n")
    f.write(u"1. 本脚本仅读取面积，不修改原始图层。\n")
    f.write(u"2. 面积单位为平方米，亩数按 1亩 = 666.6667平方米换算。\n")
    f.write(u"3. 若道路交通用地是线图层，则只统计数量，不统计面积。\n")
    f.write(u"4. 若某图层未被识别，请检查图层名称是否与 target_layers 中的名称完全一致。\n")

print u""
print u"统计完成。"
print u"结果文件位置："
print out_txt

print u""
print u"本次匹配到的目标图层："
for name in found_layers:
    print u" - " + name