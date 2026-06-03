# -*- coding: utf-8 -*-

import sys
import arcpy
import os
import codecs

reload(sys)
sys.setdefaultencoding('utf-8')

arcpy.env.overwriteOutput = True

out_folder = r"D:\SRT_ArcPy_Result"
if not os.path.exists(out_folder):
    os.makedirs(out_folder)

out_fc = os.path.join(out_folder, "suitability_eval.shp")
out_txt = os.path.join(out_folder, "suitability_summary.txt")

if arcpy.Exists(out_fc):
    arcpy.Delete_management(out_fc)

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

parcel_layers = [
    [u"农业生产用地", "AGRI", u"农业生产用地"],
    [u"科研试验用地", "SCI", u"科研试验用地"],
    [u"设施农业用地", "FAC", u"设施农业用地"]
]

water_layer_name = u"水域水源用地"
road_layer_name = u"道路交通用地"
service_layer_name = u"建设服务用地"

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

def service_score(d):
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

def type_score(code):
    if code == "SCI":
        return 5
    elif code == "AGRI":
        return 4
    elif code == "FAC":
        return 4
    else:
        return 3

def suit_level(score):
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

water_lyr = get_layer(water_layer_name)
road_lyr = get_layer(road_layer_name)
service_lyr = get_layer(service_layer_name)

if water_lyr is None:
    raise Exception(u"未找到图层：水域水源用地")
if road_lyr is None:
    raise Exception(u"未找到图层：道路交通用地")
if service_lyr is None:
    raise Exception(u"未找到图层：建设服务用地")

water_geoms = get_geoms(water_lyr.dataSource)
road_geoms = get_geoms(road_lyr.dataSource)
service_geoms = get_geoms(service_lyr.dataSource)

first_lyr = None
for item in parcel_layers:
    first_lyr = get_layer(item[0])
    if first_lyr is not None:
        break

if first_lyr is None:
    raise Exception(u"未找到核心地块图层。")

sr = arcpy.Describe(first_lyr.dataSource).spatialReference

arcpy.CreateFeatureclass_management(out_folder, "suitability_eval.shp", "POLYGON", "", "DISABLED", "DISABLED", sr)

arcpy.AddField_management(out_fc, "LTYPE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_M2", "DOUBLE")
arcpy.AddField_management(out_fc, "AREA_MU", "DOUBLE")
arcpy.AddField_management(out_fc, "DWATER", "DOUBLE")
arcpy.AddField_management(out_fc, "DROAD", "DOUBLE")
arcpy.AddField_management(out_fc, "DSERV", "DOUBLE")
arcpy.AddField_management(out_fc, "SWATER", "SHORT")
arcpy.AddField_management(out_fc, "SROAD", "SHORT")
arcpy.AddField_management(out_fc, "SSERV", "SHORT")
arcpy.AddField_management(out_fc, "STYPE", "SHORT")
arcpy.AddField_management(out_fc, "SUIT_SC", "DOUBLE")
arcpy.AddField_management(out_fc, "SUIT_LVL", "TEXT", field_length=10)

stats_type = {}
stats_level = {}

with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "LTYPE", "AREA_M2", "AREA_MU", "DWATER", "DROAD", "DSERV", "SWATER", "SROAD", "SSERV", "STYPE", "SUIT_SC", "SUIT_LVL"]) as icur:

    for item in parcel_layers:
        layer_name = item[0]
        type_code = item[1]
        type_cn = item[2]

        lyr = get_layer(layer_name)
        if lyr is None:
            continue

        stats_type[type_code] = {
            "cn": type_cn,
            "count": 0,
            "area_m2": 0.0,
            "area_mu": 0.0,
            "sum_score": 0.0
        }

        with arcpy.da.SearchCursor(lyr.dataSource, ["SHAPE@"]) as cur:
            for row in cur:
                geom = row[0]
                if geom is None:
                    continue

                area_m2 = geom.area
                area_mu = area_m2 / 666.6667

                dw = min_dist(geom, water_geoms)
                dr = min_dist(geom, road_geoms)
                ds = min_dist(geom, service_geoms)

                sw = water_score(dw)
                sr_score = road_score(dr)
                ss = service_score(ds)
                st = type_score(type_code)

                # 综合适宜性：水源 0.35，道路 0.30，建设服务支撑 0.20，地块类型基础适宜性 0.15
                suit_sc = sw * 0.35 + sr_score * 0.30 + ss * 0.20 + st * 0.15
                suit_lv = suit_level(suit_sc)

                icur.insertRow([geom, type_code, area_m2, area_mu, dw, dr, ds, sw, sr_score, ss, st, suit_sc, suit_lv])

                stats_type[type_code]["count"] += 1
                stats_type[type_code]["area_m2"] += area_m2
                stats_type[type_code]["area_mu"] += area_mu
                stats_type[type_code]["sum_score"] += suit_sc

                key = type_code + "_" + suit_lv
                if key not in stats_level:
                    stats_level[key] = {
                        "cn": type_cn,
                        "level": suit_lv,
                        "count": 0,
                        "area_m2": 0.0,
                        "area_mu": 0.0
                    }

                stats_level[key]["count"] += 1
                stats_level[key]["area_m2"] += area_m2
                stats_level[key]["area_mu"] += area_mu

with codecs.open(out_txt, "w", "utf-8") as f:
    f.write(u"白马基地核心地块综合适宜性评价结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、评价说明\n")
    f.write(u"本次综合适宜性评价综合考虑四个因素：距水源距离、水源服务评分、道路可达性评分、建设服务支撑条件以及地块类型基础适宜性。\n")
    f.write(u"权重设置为：水源 0.35，道路 0.30，建设服务支撑 0.20，地块类型基础适宜性 0.15。\n\n")

    f.write(u"二、各类核心地块平均综合适宜性得分\n")
    f.write(u"地块类型\t数量\t面积_平方米\t面积_亩\t平均综合适宜性得分\n")

    for key in stats_type:
        s = stats_type[key]
        avg_score = s["sum_score"] / s["count"] if s["count"] > 0 else 0

        f.write(u"{}\t{}\t{:.2f}\t{:.2f}\t{:.2f}\n".format(
            s["cn"], s["count"], s["area_m2"], s["area_mu"], avg_score
        ))

    f.write(u"\n三、不同综合适宜性等级面积统计\n")
    f.write(u"地块类型\t适宜性等级\t数量\t面积_平方米\t面积_亩\n")

    for key in stats_level:
        s = stats_level[key]
        f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\n".format(
            s["cn"], level_cn(s["level"]), s["count"], s["area_m2"], s["area_mu"]
        ))

    f.write(u"\n四、等级划分规则\n")
    f.write(u"4.5分及以上为高，3.5-4.5为较高，2.5-3.5为中等，1.5-2.5为较低，1.5以下为低。\n")

print "done"
print out_fc
print out_txt