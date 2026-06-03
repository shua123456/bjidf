# -*- coding: utf-8 -*-

import sys
import arcpy
import os
import codecs

reload(sys)
sys.setdefaultencoding('utf-8')

arcpy.env.overwriteOutput = True

# ==============================
# 1. 输出路径
# ==============================

out_folder = r"D:\SRT_ArcPy_Result"

if not os.path.exists(out_folder):
    os.makedirs(out_folder)

out_fc = os.path.join(out_folder, "core_access.shp")
out_txt = os.path.join(out_folder, "core_access_summary.txt")

if arcpy.Exists(out_fc):
    arcpy.Delete_management(out_fc)

# ==============================
# 2. 当前 ArcMap 工程
# ==============================

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

# ==============================
# 3. 图层名称
# ==============================

parcel_layers = [
    [u"农业生产用地", "AGRI", u"农业生产用地"],
    [u"科研试验用地", "SCI", u"科研试验用地"],
    [u"设施农业用地", "FAC", u"设施农业用地"]
]

water_layer_name = u"水域水源用地"
road_layer_name = u"道路交通用地"

# ==============================
# 4. 工具函数
# ==============================

def get_layer(name):
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.isFeatureLayer and lyr.name == name:
            return lyr
    return None

def get_geoms(fc):
    geoms = []
    with arcpy.da.SearchCursor(fc, ["SHAPE@"]) as cur:
        for row in cur:
            if row[0] is not None:
                geoms.append(row[0])
    return geoms

def min_dist(geom, targets):
    min_d = None
    for tg in targets:
        try:
            d = geom.distanceTo(tg)
            if min_d is None or d < min_d:
                min_d = d
        except:
            pass
    if min_d is None:
        return -1.0
    return float(min_d)

def water_score(d):
    if d < 0:
        return 0
    elif d <= 50:
        return 5
    elif d <= 100:
        return 4
    elif d <= 200:
        return 3
    elif d <= 400:
        return 2
    else:
        return 1

def road_score(d):
    if d < 0:
        return 0
    elif d <= 30:
        return 5
    elif d <= 60:
        return 4
    elif d <= 100:
        return 3
    elif d <= 200:
        return 2
    else:
        return 1

def access_level(score):
    if score >= 4.5:
        return "HIGH"
    elif score >= 3.5:
        return "GOOD"
    elif score >= 2.5:
        return "MID"
    elif score >= 1.5:
        return "LOW"
    else:
        return "POOR"

def level_cn(level):
    if level == "HIGH":
        return u"高"
    elif level == "GOOD":
        return u"较高"
    elif level == "MID":
        return u"中等"
    elif level == "LOW":
        return u"较低"
    elif level == "POOR":
        return u"低"
    else:
        return u"未知"

# ==============================
# 5. 获取水源和道路图层
# ==============================

water_lyr = get_layer(water_layer_name)
road_lyr = get_layer(road_layer_name)

if water_lyr is None:
    raise Exception(u"未找到图层：水域水源用地")

if road_lyr is None:
    raise Exception(u"未找到图层：道路交通用地")

water_geoms = get_geoms(water_lyr.dataSource)
road_geoms = get_geoms(road_lyr.dataSource)

print "water features: " + str(len(water_geoms))
print "road features: " + str(len(road_geoms))

# ==============================
# 6. 创建输出图层
# ==============================

first_lyr = None
for item in parcel_layers:
    first_lyr = get_layer(item[0])
    if first_lyr is not None:
        break

if first_lyr is None:
    raise Exception(u"未找到农业生产用地、科研试验用地或设施农业用地。")

sr = arcpy.Describe(first_lyr.dataSource).spatialReference

arcpy.CreateFeatureclass_management(
    out_folder,
    "core_access.shp",
    "POLYGON",
    "",
    "DISABLED",
    "DISABLED",
    sr
)

# Shapefile 字段名不能太长，所以都用短字段
arcpy.AddField_management(out_fc, "LTYPE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_M2", "DOUBLE")
arcpy.AddField_management(out_fc, "AREA_MU", "DOUBLE")
arcpy.AddField_management(out_fc, "DWATER", "DOUBLE")
arcpy.AddField_management(out_fc, "SWATER", "SHORT")
arcpy.AddField_management(out_fc, "DROAD", "DOUBLE")
arcpy.AddField_management(out_fc, "SROAD", "SHORT")
arcpy.AddField_management(out_fc, "SCORE", "DOUBLE")
arcpy.AddField_management(out_fc, "LEVEL", "TEXT", field_length=10)

insert_fields = [
    "SHAPE@",
    "LTYPE",
    "AREA_M2",
    "AREA_MU",
    "DWATER",
    "SWATER",
    "DROAD",
    "SROAD",
    "SCORE",
    "LEVEL"
]

# ==============================
# 7. 逐地块计算可达性
# ==============================

stats_type = {}
stats_level = {}

with arcpy.da.InsertCursor(out_fc, insert_fields) as icur:

    for item in parcel_layers:

        layer_name = item[0]
        type_code = item[1]
        type_cn = item[2]

        lyr = get_layer(layer_name)

        if lyr is None:
            print "skip layer"
            continue

        fc = lyr.dataSource

        stats_type[type_code] = {
            "cn": type_cn,
            "count": 0,
            "area_m2": 0.0,
            "area_mu": 0.0,
            "sum_dw": 0.0,
            "sum_dr": 0.0,
            "sum_score": 0.0
        }

        print "processing: " + type_code

        with arcpy.da.SearchCursor(fc, ["SHAPE@"]) as cur:
            for row in cur:

                geom = row[0]

                if geom is None:
                    continue

                area_m2 = geom.area
                area_mu = area_m2 / 666.6667

                dw = min_dist(geom, water_geoms)
                dr = min_dist(geom, road_geoms)

                sw = water_score(dw)
                sr_score = road_score(dr)

                # 使用中期报告中“距水源距离”和“交通条件”的 AHP 权重：
                # 距水源距离 0.050，交通条件 0.092
                score = (sw * 0.050 + sr_score * 0.092) / (0.050 + 0.092)

                level = access_level(score)

                icur.insertRow([
                    geom,
                    type_code,
                    area_m2,
                    area_mu,
                    dw,
                    sw,
                    dr,
                    sr_score,
                    score,
                    level
                ])

                stats_type[type_code]["count"] += 1
                stats_type[type_code]["area_m2"] += area_m2
                stats_type[type_code]["area_mu"] += area_mu
                stats_type[type_code]["sum_dw"] += dw
                stats_type[type_code]["sum_dr"] += dr
                stats_type[type_code]["sum_score"] += score

                key = type_code + "_" + level

                if key not in stats_level:
                    stats_level[key] = {
                        "cn": type_cn,
                        "level": level,
                        "count": 0,
                        "area_m2": 0.0,
                        "area_mu": 0.0
                    }

                stats_level[key]["count"] += 1
                stats_level[key]["area_m2"] += area_m2
                stats_level[key]["area_mu"] += area_mu

# ==============================
# 8. 输出统计报告
# ==============================

with codecs.open(out_txt, "w", "utf-8") as f:

    f.write(u"白马基地核心地块水源与道路可达性评价结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、分析说明\n")
    f.write(u"本次分析以农业生产用地、科研试验用地和设施农业用地为核心地块对象，分别计算各地块至最近水源和最近道路的距离，并结合中期报告中的AHP权重进行综合可达性评分。\n\n")

    f.write(u"二、评价规则\n")
    f.write(u"距水源距离评分：0-50m=5，50-100m=4，100-200m=3，200-400m=2，400m以上=1。\n")
    f.write(u"距道路距离评分：0-30m=5，30-60m=4，60-100m=3，100-200m=2，200m以上=1。\n")
    f.write(u"综合可达性得分 = 水源评分×0.050 + 道路评分×0.092，再除以0.142进行归一化。\n\n")

    f.write(u"三、各类核心地块平均可达性统计\n")
    f.write(u"地块类型\t数量\t面积_平方米\t面积_亩\t平均距水源_m\t平均距道路_m\t平均可达性得分\n")

    for key in stats_type:

        s = stats_type[key]
        count = s["count"]

        if count > 0:
            avg_dw = s["sum_dw"] / count
            avg_dr = s["sum_dr"] / count
            avg_score = s["sum_score"] / count
        else:
            avg_dw = 0
            avg_dr = 0
            avg_score = 0

        f.write(u"{}\t{}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\n".format(
            s["cn"],
            count,
            s["area_m2"],
            s["area_mu"],
            avg_dw,
            avg_dr,
            avg_score
        ))

    f.write(u"\n四、不同可达性等级面积统计\n")
    f.write(u"地块类型\t等级\t数量\t面积_平方米\t面积_亩\n")

    for key in stats_level:

        s = stats_level[key]

        f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\n".format(
            s["cn"],
            level_cn(s["level"]),
            s["count"],
            s["area_m2"],
            s["area_mu"]
        ))

    f.write(u"\n五、结果文件\n")
    f.write(u"核心地块可达性评价图层：D:\\SRT_ArcPy_Result\\core_access.shp\n")

print "done"
print out_fc
print out_txt