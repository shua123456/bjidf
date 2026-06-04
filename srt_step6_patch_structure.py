# -*- coding: utf-8 -*-

import sys
import arcpy
import os
import codecs
import math

reload(sys)
sys.setdefaultencoding('utf-8')

arcpy.env.overwriteOutput = True

out_folder = r"D:\SRT_ArcPy_Result"
if not os.path.exists(out_folder):
    os.makedirs(out_folder)

out_fc = os.path.join(out_folder, "patch_structure_eval.shp")
out_txt = os.path.join(out_folder, "patch_structure_summary.txt")

if arcpy.Exists(out_fc):
    arcpy.Delete_management(out_fc)

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

target_layers = [
    [u"农业生产用地", "AGRI", u"农业生产用地"],
    [u"科研试验用地", "SCI", u"科研试验用地"],
    [u"设施农业用地", "FAC", u"设施农业用地"]
]

def get_layer(name):
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.isFeatureLayer and lyr.name == name:
            return lyr
    return None

def area_level(area_mu):
    if area_mu < 2:
        return "TINY"
    elif area_mu < 5:
        return "SMALL"
    elif area_mu < 10:
        return "MID"
    elif area_mu < 20:
        return "LARGE"
    else:
        return "XLARGE"

def area_level_cn(code):
    if code == "TINY":
        return u"零散小地块"
    elif code == "SMALL":
        return u"小型地块"
    elif code == "MID":
        return u"中型地块"
    elif code == "LARGE":
        return u"较大地块"
    elif code == "XLARGE":
        return u"大型地块"
    else:
        return u"未知"

first_lyr = None
for item in target_layers:
    first_lyr = get_layer(item[0])
    if first_lyr is not None:
        break

if first_lyr is None:
    raise Exception(u"未找到农业生产用地、科研试验用地或设施农业用地图层。")

sr = arcpy.Describe(first_lyr.dataSource).spatialReference

arcpy.CreateFeatureclass_management(
    out_folder,
    "patch_structure_eval.shp",
    "POLYGON",
    "",
    "DISABLED",
    "DISABLED",
    sr
)

arcpy.AddField_management(out_fc, "TYPE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_M2", "DOUBLE")
arcpy.AddField_management(out_fc, "AREA_MU", "DOUBLE")
arcpy.AddField_management(out_fc, "PERIM", "DOUBLE")
arcpy.AddField_management(out_fc, "COMPACT", "DOUBLE")
arcpy.AddField_management(out_fc, "AREA_LVL", "TEXT", field_length=10)

insert_fields = ["SHAPE@", "TYPE", "AREA_M2", "AREA_MU", "PERIM", "COMPACT", "AREA_LVL"]

stats = {}
level_stats = {}

for item in target_layers:
    layer_name = item[0]
    type_code = item[1]
    type_cn = item[2]

    lyr = get_layer(layer_name)
    if lyr is None:
        continue

    stats[type_code] = {
        "cn": type_cn,
        "count": 0,
        "area_m2": 0.0,
        "area_mu": 0.0,
        "areas": [],
        "compact_values": []
    }

    for lv in ["TINY", "SMALL", "MID", "LARGE", "XLARGE"]:
        level_stats[(type_code, lv)] = {
            "count": 0,
            "area_mu": 0.0,
            "area_m2": 0.0
        }

with arcpy.da.InsertCursor(out_fc, insert_fields) as icur:

    for item in target_layers:
        layer_name = item[0]
        type_code = item[1]

        lyr = get_layer(layer_name)
        if lyr is None:
            continue

        with arcpy.da.SearchCursor(lyr.dataSource, ["SHAPE@"]) as cur:
            for row in cur:
                geom = row[0]
                if geom is None:
                    continue

                area_m2 = float(geom.area)
                area_mu = area_m2 / 666.6667
                perim = float(geom.length)

                if perim > 0:
                    compact = 4.0 * math.pi * area_m2 / (perim * perim)
                else:
                    compact = 0.0

                lv = area_level(area_mu)

                icur.insertRow([geom, type_code, area_m2, area_mu, perim, compact, lv])

                stats[type_code]["count"] += 1
                stats[type_code]["area_m2"] += area_m2
                stats[type_code]["area_mu"] += area_mu
                stats[type_code]["areas"].append(area_mu)
                stats[type_code]["compact_values"].append(compact)

                level_stats[(type_code, lv)]["count"] += 1
                level_stats[(type_code, lv)]["area_mu"] += area_mu
                level_stats[(type_code, lv)]["area_m2"] += area_m2

def mean(values):
    if len(values) == 0:
        return 0.0
    return sum(values) / float(len(values))

def std(values):
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    s = 0.0
    for v in values:
        s += (v - m) * (v - m)
    return math.sqrt(s / float(len(values) - 1))

with codecs.open(out_txt, "w", "utf-8") as f:
    f.write(u"白马基地核心地块空间结构与破碎化分析结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、分析说明\n")
    f.write(u"本次分析以农业生产用地、科研试验用地和设施农业用地为对象，统计各类核心地块的数量、面积规模、面积离散程度和形状紧凑度，用于判断地块零散化、连片性和规模化利用条件。\n\n")

    f.write(u"二、面积等级划分规则\n")
    f.write(u"零散小地块：小于2亩；小型地块：2-5亩；中型地块：5-10亩；较大地块：10-20亩；大型地块：20亩及以上。\n\n")

    f.write(u"三、核心地块空间结构统计\n")
    f.write(u"地块类型\t数量\t总面积_亩\t平均面积_亩\t最小面积_亩\t最大面积_亩\t面积标准差\t面积变异系数\t平均紧凑度\n")

    for key in ["AGRI", "SCI", "FAC"]:
        if key not in stats:
            continue

        s = stats[key]
        areas = s["areas"]
        compacts = s["compact_values"]

        if len(areas) == 0:
            continue

        avg_area = mean(areas)
        min_area = min(areas)
        max_area = max(areas)
        sd_area = std(areas)

        if avg_area > 0:
            cv_area = sd_area / avg_area
        else:
            cv_area = 0.0

        avg_compact = mean(compacts)

        f.write(u"{}\t{}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.3f}\n".format(
            s["cn"], s["count"], s["area_mu"], avg_area,
            min_area, max_area, sd_area, cv_area, avg_compact
        ))

    f.write(u"\n四、不同面积等级地块统计\n")
    f.write(u"地块类型\t面积等级\t数量\t面积_亩\t面积占比_%\n")

    for key in ["AGRI", "SCI", "FAC"]:
        if key not in stats:
            continue
        total_mu = stats[key]["area_mu"]

        for lv in ["TINY", "SMALL", "MID", "LARGE", "XLARGE"]:
            ls = level_stats[(key, lv)]
            if total_mu > 0:
                pct = ls["area_mu"] / total_mu * 100.0
            else:
                pct = 0.0

            f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\n".format(
                stats[key]["cn"], area_level_cn(lv),
                ls["count"], ls["area_mu"], pct
            ))

    f.write(u"\n五、结果文件\n")
    f.write(u"D:\\SRT_ArcPy_Result\\patch_structure_eval.shp\n")

print "done"
print out_fc
print out_txt