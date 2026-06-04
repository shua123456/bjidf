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

out_fc = os.path.join(out_folder, "water_service_coverage.shp")
out_txt = os.path.join(out_folder, "water_service_coverage_summary.txt")

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

def water_zone(d):
    if d < 0:
        return "UNKNOWN"
    elif d <= 50:
        return "W50"
    elif d <= 100:
        return "W100"
    elif d <= 200:
        return "W200"
    elif d <= 400:
        return "W400"
    else:
        return "WOUT"

def service_zone(d):
    if d < 0:
        return "UNKNOWN"
    elif d <= 100:
        return "S100"
    elif d <= 200:
        return "S200"
    elif d <= 400:
        return "S400"
    else:
        return "SOUT"

def water_zone_cn(z):
    if z == "W50":
        return u"0-50m"
    elif z == "W100":
        return u"50-100m"
    elif z == "W200":
        return u"100-200m"
    elif z == "W400":
        return u"200-400m"
    elif z == "WOUT":
        return u"400m以上"
    else:
        return u"未知"

def service_zone_cn(z):
    if z == "S100":
        return u"0-100m"
    elif z == "S200":
        return u"100-200m"
    elif z == "S400":
        return u"200-400m"
    elif z == "SOUT":
        return u"400m以上"
    else:
        return u"未知"

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
service_lyr = get_layer_from_names(service_layer_names)

if water_lyr is None:
    raise Exception(u"未找到图层：水域水源用地")

if service_lyr is None:
    raise Exception(u"未找到图层：建设服务用地 或 综合服务设施用地")

water_geoms = get_geoms(water_lyr.dataSource)
service_geoms = get_geoms(service_lyr.dataSource)

first_lyr = None
for item in core_layers:
    first_lyr = get_layer(item[0])
    if first_lyr is not None:
        break

if first_lyr is None:
    raise Exception(u"未找到核心地块图层。")

sr = arcpy.Describe(first_lyr.dataSource).spatialReference

arcpy.CreateFeatureclass_management(
    out_folder,
    "water_service_coverage.shp",
    "POLYGON",
    "",
    "DISABLED",
    "DISABLED",
    sr
)

arcpy.AddField_management(out_fc, "TYPE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "AREA_MU", "DOUBLE")
arcpy.AddField_management(out_fc, "DWATER", "DOUBLE")
arcpy.AddField_management(out_fc, "DSERV", "DOUBLE")
arcpy.AddField_management(out_fc, "W_ZONE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "S_ZONE", "TEXT", field_length=10)
arcpy.AddField_management(out_fc, "COMB", "TEXT", field_length=15)
arcpy.AddField_management(out_fc, "COMB_CN", "TEXT", field_length=40)

insert_fields = [
    "SHAPE@", "TYPE", "AREA_MU",
    "DWATER", "DSERV",
    "W_ZONE", "S_ZONE",
    "COMB", "COMB_CN"
]

water_stats = {}
service_stats = {}
comb_stats = {}
type_comb_stats = {}

type_cn_map = {
    "AGRI": u"农业生产用地",
    "SCI": u"科研试验用地",
    "FAC": u"设施农业用地"
}

for key in ["AGRI", "SCI", "FAC"]:
    for z in ["W50", "W100", "W200", "W400", "WOUT"]:
        water_stats[(key, z)] = {"count": 0, "area": 0.0}

    for z in ["S100", "S200", "S400", "SOUT"]:
        service_stats[(key, z)] = {"count": 0, "area": 0.0}

    type_comb_stats[key] = {
        "total": 0.0,
        "BOTH_GOOD": 0.0,
        "NORMAL": 0.0,
        "WATER_WEAK": 0.0,
        "SERV_WEAK": 0.0,
        "BOTH_WEAK": 0.0,
        "UNKNOWN": 0.0
    }

for c in ["BOTH_GOOD", "NORMAL", "WATER_WEAK", "SERV_WEAK", "BOTH_WEAK", "UNKNOWN"]:
    comb_stats[c] = {"cn": "", "count": 0, "area": 0.0}

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
                ds = min_dist(geom, service_geoms)

                wz = water_zone(dw)
                sz = service_zone(ds)

                comb, comb_cn = combined_class(dw, ds)

                icur.insertRow([
                    geom, type_code, area_mu,
                    dw, ds,
                    wz, sz,
                    comb, comb_cn
                ])

                if (type_code, wz) in water_stats:
                    water_stats[(type_code, wz)]["count"] += 1
                    water_stats[(type_code, wz)]["area"] += area_mu

                if (type_code, sz) in service_stats:
                    service_stats[(type_code, sz)]["count"] += 1
                    service_stats[(type_code, sz)]["area"] += area_mu

                comb_stats[comb]["cn"] = comb_cn
                comb_stats[comb]["count"] += 1
                comb_stats[comb]["area"] += area_mu

                type_comb_stats[type_code]["total"] += area_mu
                type_comb_stats[type_code][comb] += area_mu

with codecs.open(out_txt, "w", "utf-8") as f:
    f.write(u"白马基地核心地块水源与综合服务设施覆盖分析结果\n")
    f.write(u"====================================\n\n")

    f.write(u"一、分析说明\n")
    f.write(u"本次分析以农业生产用地、科研试验用地和设施农业用地为对象，分别计算核心地块至最近水域水源用地和综合服务设施用地的距离，并统计不同服务半径内的面积分布。\n\n")

    f.write(u"二、水源覆盖分级统计\n")
    f.write(u"地块类型\t水源距离等级\t数量\t面积_亩\t面积占比_%\n")

    for key in ["AGRI", "SCI", "FAC"]:
        total = 0.0
        for z in ["W50", "W100", "W200", "W400", "WOUT"]:
            total += water_stats[(key, z)]["area"]

        for z in ["W50", "W100", "W200", "W400", "WOUT"]:
            area = water_stats[(key, z)]["area"]
            if total > 0:
                pct = area / total * 100.0
            else:
                pct = 0.0

            f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\n".format(
                type_cn_map[key],
                water_zone_cn(z),
                water_stats[(key, z)]["count"],
                area,
                pct
            ))

    f.write(u"\n三、综合服务设施覆盖分级统计\n")
    f.write(u"地块类型\t服务设施距离等级\t数量\t面积_亩\t面积占比_%\n")

    for key in ["AGRI", "SCI", "FAC"]:
        total = 0.0
        for z in ["S100", "S200", "S400", "SOUT"]:
            total += service_stats[(key, z)]["area"]

        for z in ["S100", "S200", "S400", "SOUT"]:
            area = service_stats[(key, z)]["area"]
            if total > 0:
                pct = area / total * 100.0
            else:
                pct = 0.0

            f.write(u"{}\t{}\t{}\t{:.2f}\t{:.2f}\n".format(
                type_cn_map[key],
                service_zone_cn(z),
                service_stats[(key, z)]["count"],
                area,
                pct
            ))

    f.write(u"\n四、水源与服务设施组合覆盖类型统计\n")
    f.write(u"组合类型\t数量\t面积_亩\t面积占比_%\n")

    total_comb = 0.0
    for c in comb_stats:
        total_comb += comb_stats[c]["area"]

    for c in ["BOTH_GOOD", "NORMAL", "WATER_WEAK", "SERV_WEAK", "BOTH_WEAK", "UNKNOWN"]:
        area = comb_stats[c]["area"]
        if total_comb > 0:
            pct = area / total_comb * 100.0
        else:
            pct = 0.0

        f.write(u"{}\t{}\t{:.2f}\t{:.2f}\n".format(
            comb_stats[c]["cn"],
            comb_stats[c]["count"],
            area,
            pct
        ))

    f.write(u"\n五、不同地块类型组合覆盖面积统计\n")
    f.write(u"地块类型\t总面积_亩\t双优覆盖_亩\t一般覆盖_亩\t水源不足_亩\t服务不足_亩\t双重不足_亩\n")

    for key in ["AGRI", "SCI", "FAC"]:
        s = type_comb_stats[key]
        f.write(u"{}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\t{:.2f}\n".format(
            type_cn_map[key],
            s["total"],
            s["BOTH_GOOD"],
            s["NORMAL"],
            s["WATER_WEAK"],
            s["SERV_WEAK"],
            s["BOTH_WEAK"]
        ))

    f.write(u"\n六、结果文件\n")
    f.write(u"D:\\SRT_ArcPy_Result\\water_service_coverage.shp\n")

print "done"
print out_fc
print out_txt