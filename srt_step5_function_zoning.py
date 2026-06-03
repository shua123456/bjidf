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

out_fc = os.path.join(out_folder, "function_zoning_eval.shp")
out_txt = os.path.join(out_folder, "function_zoning_summary.txt")

if arcpy.Exists(out_fc):
    arcpy.Delete_management(out_fc)

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

# 待评价地块图层
parcel_layers = [
    [u"农业生产用地", "AGRI", u"农业生产用地"],
    [u"科研试验用地", "SCI", u"科研试验用地"],
    [u"设施农业用地", "FAC", u"设施农业用地"],
    [u"生态绿地/林地", "ECO", u"生态绿地/林地"],
    [u"建设服务用地", "SERV", u"建设服务用地"]
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

# 1-9 等级赋值，靠近水源越适宜
def score_water(d):
    if d < 0:
        return 1
    elif d <= 50:
        return 9
    elif d <= 100:
        return 7
    elif d <= 200:
        return 5
    elif d <= 400:
        return 3
    else:
        return 1

# 1-9 等级赋值，靠近道路越适宜
def score_road(d):
    if d < 0:
        return 1
    elif d <= 30:
        return 9
    elif d <= 60:
        return 7
    elif d <= 100:
        return 5
    elif d <= 200:
        return 3
    else:
        return 1

# 1-9 等级赋值，靠近建设服务用地越适宜
def score_service(d):
    if d < 0:
        return 1
    elif d <= 50:
        return 9
    elif d <= 100:
        return 7
    elif d <= 200:
        return 5
    elif d <= 400:
        return 3
    else:
        return 1

# 地块规模评分，面积越大越适合生产、生态和集中开发
def score_area(area_mu):
    if area_mu >= 20:
        return 9
    elif area_mu >= 10:
        return 7
    elif area_mu >= 5:
        return 5
    elif area_mu >= 2:
        return 3
    else:
        return 1

# 土地利用现状对不同功能区的基础适宜性赋值
def landuse_score(src_code, func_code):
    table = {
        "AGRI": {"AGRI":9, "SCI":5, "FAC":5, "ECO":3, "SERV":1},
        "SCI":  {"AGRI":5, "SCI":9, "FAC":5, "ECO":3, "SERV":3},
        "FAC":  {"AGRI":5, "SCI":7, "FAC":9, "ECO":1, "SERV":5},
        "ECO":  {"AGRI":3, "SCI":3, "FAC":1, "ECO":9, "SERV":3},
        "SERV": {"AGRI":1, "SCI":5, "FAC":5, "ECO":3, "SERV":9}
    }
    return table[src_code][func_code]

# 不同功能区权重：土地现状、水源、道路、建设服务、地块规模
weights = {
    "AGRI": {"land":0.30, "water":0.30, "road":0.15, "serv":0.05, "area":0.20},
    "SCI":  {"land":0.35, "water":0.20, "road":0.15, "serv":0.20, "area":0.10},
    "FAC":  {"land":0.35, "water":0.20, "road":0.25, "serv":0.15, "area":0.05},
    "ECO":  {"land":0.45, "water":0.20, "road":0.05, "serv":0.05, "area":0.25},
    "SERV": {"land":0.40, "water":0.05, "road":0.25, "serv":0.20, "area":0.10}
}

def calc_score(src_code, func_code, sw, sr, ss, sa):
    w = weights[func_code]
    sl = landuse_score(src_code, func_code)
    return sl*w["land"] + sw*w["water"] + sr*w["road"] + ss*w["serv"] + sa*w["area"]

def best_function(scores):
    best_code = None
    best_score = -999
    for k in scores:
        if scores[k] > best_score:
            best_score = scores[k]
            best_code = k
    return best_code, best_score

def func_cn(code):
    if code == "AGRI":
        return u"高效农业生产区"
    elif code == "SCI":
        return u"科研试验示范区"
    elif code == "FAC":
        return u"设施农业发展区"
    elif code == "ECO":
        return u"生态景观保育区"
    elif code == "SERV":
        return u"综合服务支撑区"
    else:
        return u"未知"

# 获取基础因子图层
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
    raise Exception(u"未找到待评价地块图层。")

sr = arcpy.Describe(first_lyr.dataSource).spatialReference

arcpy.CreateFeatureclass_management(out_folder, "function_zoning_eval.shp", "POLYGON", "", "DISABLED", "DISABLED", sr)

# 字段名不超过 10 个字符
arcpy.AddField_management(out_fc, "SRC", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_M2", "DOUBLE")
arcpy.AddField_management(out_fc, "AREA_MU", "DOUBLE")
arcpy.AddField_management(out_fc, "DWATER", "DOUBLE")
arcpy.AddField_management(out_fc, "DROAD", "DOUBLE")
arcpy.AddField_management(out_fc, "DSERV", "DOUBLE")
arcpy.AddField_management(out_fc, "F_WATER", "SHORT")
arcpy.AddField_management(out_fc, "F_ROAD", "SHORT")
arcpy.AddField_management(out_fc, "F_SERV", "SHORT")
arcpy.AddField_management(out_fc, "F_AREA", "SHORT")
arcpy.AddField_management(out_fc, "S_AGRI", "DOUBLE")
arcpy.AddField_management(out_fc, "S_SCI", "DOUBLE")
arcpy.AddField_management(out_fc, "S_FAC", "DOUBLE")
arcpy.AddField_management(out_fc, "S_ECO", "DOUBLE")
arcpy.AddField_management(out_fc, "S_SERV", "DOUBLE")
arcpy.AddField_management(out_fc, "BEST", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "BEST_SC", "DOUBLE")

insert_fields = [
    "SHAPE@", "SRC", "AREA_M2", "AREA_MU",
    "DWATER", "DROAD", "DSERV",
    "F_WATER", "F_ROAD", "F_SERV", "F_AREA",
    "S_AGRI", "S_SCI", "S_FAC", "S_ECO", "S_SERV",
    "BEST", "BEST_SC"
]

stats_best = {}
stats_src = {}

with arcpy.da.InsertCursor(out_fc, insert_fields) as icur:

    for item in parcel_layers:
        layer_name = item[0]
        src_code = item[1]
        src_cn = item[2]

        lyr = get_layer(layer_name)
        if lyr is None:
            continue

        if src_code not in stats_src:
            stats_src[src_code] = {"cn": src_cn, "count":0, "area_m2":0.0, "area_mu":0.0}

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

                sw = score_water(dw)
                sr_score = score_road(dr)
                ss = score_service(ds)
                sa = score_area(area_mu)

                scores = {
                    "AGRI": calc_score(src_code, "AGRI", sw, sr_score, ss, sa),
                    "SCI":  calc_score(src_code, "SCI",  sw, sr_score, ss, sa),
                    "FAC":  calc_score(src_code, "FAC",  sw, sr_score, ss, sa),
                    "ECO":  calc_score(src_code, "ECO",  sw, sr_score, ss, sa),
                    "SERV": calc_score(src_code, "SERV", sw, sr_score, ss, sa)
                }

                best_code, best_sc = best_function(scores)

                icur.insertRow([
                    geom, src_code, area_m2, area_mu,
                    dw, dr, ds,
                    sw, sr_score, ss, sa,
                    scores["AGRI"], scores["SCI"], scores["FAC"], scores["ECO"], scores["SERV"],
                    best_code, best_sc
                ])

                stats_src[src_code]["count"] += 1
                stats_src[src_code]["area_m2"] += area_m2
                stats_src[src_code]["area_mu"] += area_mu

                if best_code not in stats_best:
                    stats_best[best_code] = {"count":0, "area_m2":0.0, "area_mu":0.0}

                stats_best[best_code]["count"] += 1
                stats_best[best_code]["area_m2"] += area_m2
                stats_best[best_code]["area_mu"] += area_mu

with codecs.open(out_txt, "w", "utf-8") as f:
    f.write(u"白马基地土地资源功能分区适宜性评价结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、方法说明\n")
    f.write(u"本次评价参考多因素综合评价与功能分区适宜性评价思路，以地块为基本评价单元，对土地利用现状、水源条件、道路交通条件、建设服务支撑条件和地块规模进行1-9等级赋值，并针对不同功能区设置权重，计算各地块对不同功能区的适宜性得分。\n\n")

    f.write(u"二、评价因子与赋值说明\n")
    f.write(u"1. 土地利用现状：依据地块现状类型判断其对农业生产、科研试验、设施农业、生态景观和综合服务功能的基础适宜性。\n")
    f.write(u"2. 水源条件：按距水源距离赋值，0-50m=9，50-100m=7，100-200m=5，200-400m=3，400m以上=1。\n")
    f.write(u"3. 道路交通条件：按距道路距离赋值，0-30m=9，30-60m=7，60-100m=5，100-200m=3，200m以上=1。\n")
    f.write(u"4. 建设服务支撑：按距建设服务用地距离赋值，0-50m=9，50-100m=7，100-200m=5，200-400m=3，400m以上=1。\n")
    f.write(u"5. 地块规模：按面积赋值，20亩以上=9，10-20亩=7，5-10亩=5，2-5亩=3，2亩以下=1。\n\n")

    f.write(u"三、不同功能区权重设置\n")
    f.write(u"功能类型\t土地现状\t水源条件\t道路条件\t建设服务\t地块规模\n")
    f.write(u"高效农业生产区\t0.30\t0.30\t0.15\t0.05\t0.20\n")
    f.write(u"科研试验示范区\t0.35\t0.20\t0.15\t0.20\t0.10\n")
    f.write(u"设施农业发展区\t0.35\t0.20\t0.25\t0.15\t0.05\n")
    f.write(u"生态景观保育区\t0.45\t0.20\t0.05\t0.05\t0.25\n")
    f.write(u"综合服务支撑区\t0.40\t0.05\t0.25\t0.20\t0.10\n\n")

    f.write(u"四、现状地块统计\n")
    f.write(u"现状类型\t数量\t面积_平方米\t面积_亩\n")
    for key in stats_src:
        s = stats_src[key]
        f.write(u"{}\t{}\t{:.2f}\t{:.2f}\n".format(
            s["cn"], s["count"], s["area_m2"], s["area_mu"]
        ))

    f.write(u"\n五、推荐功能分区统计\n")
    f.write(u"推荐功能类型\t数量\t面积_平方米\t面积_亩\n")
    for key in stats_best:
        s = stats_best[key]
        f.write(u"{}\t{}\t{:.2f}\t{:.2f}\n".format(
            func_cn(key), s["count"], s["area_m2"], s["area_mu"]
        ))

    f.write(u"\n六、结果文件\n")
    f.write(u"D:\\SRT_ArcPy_Result\\function_zoning_eval.shp\n")

print "done"
print out_fc
print out_txt