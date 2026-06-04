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

out_fc = os.path.join(out_folder, "optimization_priority.shp")
out_txt = os.path.join(out_folder, "optimization_priority_summary.txt")

if arcpy.Exists(out_fc):
    arcpy.Delete_management(out_fc)

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

core_layers = [
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

def score_water(d):
    if d < 0:
        return 1
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

def score_road(d):
    if d < 0:
        return 1
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

def score_service(d):
    if d < 0:
        return 1
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
        return 3
    else:
        return 3

def water_level(score):
    if score == 5:
        return "HIGH"
    elif score == 4:
        return "GOOD"
    elif score == 3:
        return "MID"
    elif score == 2:
        return "LOW"
    else:
        return "VLOW"

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
        return "VLOW"

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

def priority_judge(type_code, area_mu, sw, sr, ss, st, suit):
    wl = water_level(sw)
    sl = suit_level(suit)
    al = area_level(area_mu)

    # P1：优先优化区
    if sl == "MID" or wl in ["LOW", "VLOW"]:
        return "P1", u"优先优化区", u"水源或综合适宜性短板明显", u"优先完善水源、道路和服务设施"

    # 设施农业小地块集中，是重点提升对象
    if type_code == "FAC" and al in ["TINY", "SMALL"]:
        return "P2", u"重点提升区", u"设施农业地块规模偏小", u"推进设施整合和配套共享"

    # 水源中等但综合适宜性尚可
    if wl == "MID":
        return "P2", u"重点提升区", u"水源服务条件一般", u"完善灌溉管线和蓄水点"

    # 服务支撑偏弱
    if ss <= 2:
        return "P2", u"重点提升区", u"综合服务支撑不足", u"补强服务节点和管理支撑"

    # 面积较小但不是严重短板
    if al in ["TINY", "SMALL"]:
        return "P3", u"一般优化区", u"地块规模偏小", u"优化地块组织和连片利用"

    # 综合条件较好
    return "P4", u"稳定保持区", u"综合条件较好", u"保持现有功能并适度提升管理效率"

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
for item in core_layers:
    first_lyr = get_layer(item[0])
    if first_lyr is not None:
        break

if first_lyr is None:
    raise Exception(u"未找到核心地块图层。")

sr = arcpy.Describe(first_lyr.dataSource).spatialReference

arcpy.CreateFeatureclass_management(out_folder, "optimization_priority.shp", "POLYGON", "", "DISABLED", "DISABLED", sr)

arcpy.AddField_management(out_fc, "TYPE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_MU", "DOUBLE")
arcpy.AddField_management(out_fc, "DWATER", "DOUBLE")
arcpy.AddField_management(out_fc, "DROAD", "DOUBLE")
arcpy.AddField_management(out_fc, "DSERV", "DOUBLE")
arcpy.AddField_management(out_fc, "S_WATER", "SHORT")
arcpy.AddField_management(out_fc, "S_ROAD", "SHORT")
arcpy.AddField_management(out_fc, "S_SERV", "SHORT")
arcpy.AddField_management(out_fc, "S_TYPE", "SHORT")
arcpy.AddField_management(out_fc, "SUIT", "DOUBLE")
arcpy.AddField_management(out_fc, "SUIT_LVL", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_LVL", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "PRI", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "PRI_CN", "TEXT", field_length=30)
arcpy.AddField_management(out_fc, "PROBLEM", "TEXT", field_length=60)
arcpy.AddField_management(out_fc, "ACTION", "TEXT", field_length=80)

insert_fields = [
    "SHAPE@", "TYPE", "AREA_MU",
    "DWATER", "DROAD", "DSERV",
    "S_WATER", "S_ROAD", "S_SERV", "S_TYPE",
    "SUIT", "SUIT_LVL", "AREA_LVL",
    "PRI", "PRI_CN", "PROBLEM", "ACTION"
]

stats = {}
type_stats = {}

for p in ["P1", "P2", "P3", "P4"]:
    stats[p] = {"cn": "", "count": 0, "area_mu": 0.0}

for item in core_layers:
    type_stats[item[1]] = {
        "cn": item[2],
        "count": 0,
        "area_mu": 0.0,
        "p1": 0.0,
        "p2": 0.0,
        "p3": 0.0,
        "p4": 0.0
    }

with arcpy.da.InsertCursor(out_fc, insert_fields) as icur:
    for item in core_layers:
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

                area_mu = float(geom.area) / 666.6667

                dw = min_dist(geom, water_geoms)
                dr = min_dist(geom, road_geoms)
                ds = min_dist(geom, service_geoms)

                sw = score_water(dw)
                sr_score = score_road(dr)
                ss = score_service(ds)
                st = type_score(type_code)

                suit = 0.35 * sw + 0.30 * sr_score + 0.20 * ss + 0.15 * st

                sl = suit_level(suit)
                al = area_level(area_mu)

                pri, pri_cn, problem, action = priority_judge(type_code, area_mu, sw, sr_score, ss, st, suit)

                icur.insertRow([
                    geom, type_code, area_mu,
                    dw, dr, ds,
                    sw, sr_score, ss, st,
                    suit, sl, al,
                    pri, pri_cn, problem, action
                ])

                stats[pri]["cn"] = pri_cn
                stats[pri]["count"] += 1
                stats[pri]["area_mu"] += area_mu

                type_stats[type_code]["count"] += 1
                type_stats[type_code]["area_mu"] += area_mu
                type_stats[type_code][pri.lower()] += area_mu

with codecs.open(out_txt, "w", "utf-8") as f:
    f.write(u"白马基地土地资源优化优先级识别结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、分析说明\n")
    f.write(u"本次分析以农业生产用地、科研试验用地和设施农业用地为对象，在综合适宜性评价、水源条件、服务支撑条件和地块规模分析基础上，识别不同地块的优化优先级。\n\n")

    f.write(u"二、优化优先级判定规则\n")
    f.write(u"P1 优先优化区：综合适宜性为中等，或水源条件较低、低，说明存在明显短板。\n")
    f.write(u"P2 重点提升区：设施农业小地块、水源条件中等或服务支撑不足，说明需要重点补强。\n")
    f.write(u"P3 一般优化区：综合条件较好但地块规模偏小，主要进行连片整理和管理优化。\n")
    f.write(u"P4 稳定保持区：综合条件较好，无明显短板，以保持现状功能和提升管理效率为主。\n\n")

    f.write(u"三、不同优化优先级面积统计\n")
    f.write(u"优先级\t类型\t数量\t面积_亩\t面积占比_%\n")
    total_area = sum([stats[p]["area_mu"] for p in stats])

    for p in ["P1", "P2", "P3", "P4"]:
        if total_area > 0:
            pct = stats[p]["area_mu"] / total_area * 100.0
        else:
            pct = 0.0
        f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\n".format(
            p, stats[p]["cn"], stats[p]["count"], stats[p]["area_mu"], pct
        ))

    f.write(u"\n四、不同地块类型优化优先级面积统计\n")
    f.write(u"地块类型\t总面积_亩\t优先优化区_亩\t重点提升区_亩\t一般优化区_亩\t稳定保持区_亩\n")

    for key in ["AGRI", "SCI", "FAC"]:
        s = type_stats[key]
        f.write(u"{}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\n".format(
            s["cn"], s["area_mu"], s["p1"], s["p2"], s["p3"], s["p4"]
        ))

    f.write(u"\n五、结果解释要点\n")
    f.write(u"1. 优先优化区代表当前水源条件或综合适宜性存在明显短板的地块，应作为近期优化重点。\n")
    f.write(u"2. 重点提升区主要用于识别水源、服务设施或设施农业规模化方面存在不足的地块。\n")
    f.write(u"3. 一般优化区适合通过地块整理、连片利用和管理优化进行提升。\n")
    f.write(u"4. 稳定保持区说明现有空间条件较好，后续应以保持功能和提高管理效率为主。\n\n")

    f.write(u"六、结果文件\n")
    f.write(u"D:\\SRT_ArcPy_Result\\optimization_priority.shp\n")

print "done"
print out_fc
print out_txt