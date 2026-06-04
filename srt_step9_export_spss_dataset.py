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

out_csv = os.path.join(out_folder, "spss_land_parcel_dataset.csv")

mxd = arcpy.mapping.MapDocument("CURRENT")
df = arcpy.mapping.ListDataFrames(mxd)[0]

core_layers = [
    [u"农业生产用地", "AGRI", u"农业生产用地"],
    [u"科研试验用地", "SCI", u"科研试验用地"],
    [u"设施农业用地", "FAC", u"设施农业用地"]
]

water_layer_name = u"水域水源用地"
road_layer_name = u"道路交通用地"
service_layer_names = [u"建设服务用地", u"综合服务设施用地"]

def get_layer(name):
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        if lyr.isFeatureLayer and lyr.name == name:
            return lyr
    return None

def get_layer_from_names(names):
    for name in names:
        lyr = get_layer(name)
        if lyr is not None:
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

def priority_judge(type_code, area_mu, sw, sr_score, ss, st, suit):
    sl = suit_level(suit)
    al = area_level(area_mu)

    if sl == "MID" or sw <= 2:
        return "P1", u"优先优化区"
    elif type_code == "FAC" and al in ["TINY", "SMALL"]:
        return "P2", u"重点提升区"
    elif sw == 3:
        return "P2", u"重点提升区"
    elif ss <= 2:
        return "P2", u"重点提升区"
    elif al in ["TINY", "SMALL"]:
        return "P3", u"一般优化区"
    else:
        return "P4", u"稳定保持区"

def combined_class(dw, ds):
    if dw < 0 or ds < 0:
        return "UNKNOWN", u"未知"
    elif dw <= 100 and ds <= 200:
        return "BOTH_GOOD", u"水源与服务双优覆盖"
    elif dw > 200 and ds > 400:
        return "BOTH_WEAK", u"水源与服务双重不足"
    elif dw > 200:
        return "WATER_WEAK", u"水源覆盖不足"
    elif ds > 400:
        return "SERV_WEAK", u"服务覆盖不足"
    else:
        return "NORMAL", u"一般覆盖区"

water_lyr = get_layer(water_layer_name)
road_lyr = get_layer(road_layer_name)
service_lyr = get_layer_from_names(service_layer_names)

if water_lyr is None:
    raise Exception(u"未找到图层：水域水源用地")
if road_lyr is None:
    raise Exception(u"未找到图层：道路交通用地")
if service_lyr is None:
    raise Exception(u"未找到图层：建设服务用地 或 综合服务设施用地")

water_geoms = get_geoms(water_lyr.dataSource)
road_geoms = get_geoms(road_lyr.dataSource)
service_geoms = get_geoms(service_lyr.dataSource)

headers = [
    "ID",
    "TYPE",
    "TYPE_CN",
    "AREA_MU",
    "PERIM_M",
    "COMPACT",
    "DWATER",
    "DROAD",
    "DSERV",
    "S_WATER",
    "S_ROAD",
    "S_SERV",
    "S_TYPE",
    "SUIT",
    "SUIT_LVL",
    "AREA_LVL",
    "PRI",
    "PRI_CN",
    "COMB",
    "COMB_CN",
    "TYPE_AGRI",
    "TYPE_SCI",
    "TYPE_FAC"
]

rows = []
pid = 1

for item in core_layers:
    layer_name = item[0]
    type_code = item[1]
    type_cn = item[2]

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
            pri, pri_cn = priority_judge(type_code, area_mu, sw, sr_score, ss, st, suit)
            comb, comb_cn = combined_class(dw, ds)

            type_agri = 1 if type_code == "AGRI" else 0
            type_sci = 1 if type_code == "SCI" else 0
            type_fac = 1 if type_code == "FAC" else 0

            rows.append([
                pid,
                type_code,
                type_cn,
                round(area_mu, 4),
                round(perim, 4),
                round(compact, 4),
                round(dw, 4),
                round(dr, 4),
                round(ds, 4),
                sw,
                sr_score,
                ss,
                st,
                round(suit, 4),
                sl,
                al,
                pri,
                pri_cn,
                comb,
                comb_cn,
                type_agri,
                type_sci,
                type_fac
            ])

            pid += 1

with codecs.open(out_csv, "w", "utf-8-sig") as f:
    f.write(",".join(headers) + "\n")

    for r in rows:
        line = []
        for v in r:
            if isinstance(v, unicode):
                line.append(v)
            else:
                line.append(str(v))
        f.write(",".join(line) + "\n")

print "done"
print out_csv
print "rows:", len(rows)