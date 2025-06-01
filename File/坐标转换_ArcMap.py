# -*- coding: utf-8 -*-
import arcpy
import os
import math
import sys

# 重载sys设置默认编码为UTF-8
reload(sys)
sys.setdefaultencoding('utf-8')

# ============================
# 坐标系转换函数（WGS84 <-> GCJ-02）
# ============================

PI = math.pi
AXIS = 6378245.0  # 地球长轴
EE = 0.00669342162296594323  # 偏心率平方


def out_of_china(lng, lat):
    """判断坐标是否在中国以外"""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def transform_lat(x, y):
    ret = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20 * math.sin(6 * x * PI) + 20 * math.sin(2 * x * PI)) * 2 / 3
    ret += (20 * math.sin(y * PI) + 40 * math.sin(y / 3 * PI)) * 2 / 3
    ret += (160 * math.sin(y / 12 * PI) + 320 * math.sin(y * PI / 30)) * 2 / 3
    return ret


def transform_lng(x, y):
    ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20 * math.sin(6 * x * PI) + 20 * math.sin(2 * x * PI)) * 2 / 3
    ret += (20 * math.sin(x * PI) + 40 * math.sin(x / 3 * PI)) * 2 / 3
    ret += (150 * math.sin(x / 12 * PI) + 300 * math.sin(x / 30 * PI)) * 2 / 3
    return ret


def wgs84_to_gcj02(lng, lat):
    if out_of_china(lng, lat):
        return (lng, lat)
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((AXIS * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (AXIS / sqrtmagic * math.cos(radlat) * PI)
    return (lng + dlng, lat + dlat)


def gcj02_to_wgs84(lng, lat):
    if out_of_china(lng, lat):
        return (lng, lat)
    lng2, lat2 = wgs84_to_gcj02(lng, lat)
    return (lng * 2 - lng2, lat * 2 - lat2)


# ============================
# 转换几何对象（支持点/线/面）
# ============================

def transform_geometry(geometry, transform_func):
    """应用坐标转换函数到几何对象上"""
    try:
        # 获取几何类型（确保使用ASCII字符串比较）
        shape_type = str(geometry.type).lower()

        # 点类型处理
        if shape_type == "point":
            x, y = transform_func(geometry.centroid.X, geometry.centroid.Y)
            return arcpy.PointGeometry(arcpy.Point(x, y), arcpy.SpatialReference(4326))

        # 多点和线/面类型处理
        elif shape_type in ["polyline", "polygon", "multipoint"]:
            new_geom = arcpy.Array()

            # 遍历所有部分
            for part in geometry:
                part_array = arcpy.Array()
                for pnt in part:
                    if pnt:
                        x, y = transform_func(pnt.X, pnt.Y)
                        part_array.add(arcpy.Point(x, y))
                new_geom.add(part_array)

            # 返回对应类型的几何对象
            if shape_type == "polyline":
                return arcpy.Polyline(new_geom, arcpy.SpatialReference(4326))
            elif shape_type == "polygon":
                return arcpy.Polygon(new_geom, arcpy.SpatialReference(4326))
            else:
                return arcpy.Multipoint(new_geom, arcpy.SpatialReference(4326))
        else:
            raise ValueError("不支持的几何类型: " + shape_type)
    except Exception as e:
        arcpy.AddError(u"几何转换错误: " + unicode(e))
        raise


# ============================
# 主函数：读取输入，转换，写入输出
# ============================

def main():
    try:
        # 强制设置环境编码
        reload(sys)
        sys.setdefaultencoding('utf-8')

        # 参数获取（处理中文字符路径）
        input_fc = arcpy.GetParameterAsText(0).decode('utf-8') if isinstance(arcpy.GetParameterAsText(0),
                                                                             str) else arcpy.GetParameterAsText(0)
        output_fc = arcpy.GetParameterAsText(1).decode('utf-8') if isinstance(arcpy.GetParameterAsText(1),
                                                                              str) else arcpy.GetParameterAsText(1)
        conversion_type = arcpy.GetParameterAsText(2)

        # 验证输入参数
        if not arcpy.Exists(input_fc.encode('utf-8')):
            arcpy.AddError(u"输入要素不存在！路径: " + input_fc)
            return

        # 选择转换函数
        transform_func = wgs84_to_gcj02 if conversion_type == "WGS84_TO_GCJ02" else gcj02_to_wgs84
        arcpy.AddMessage(
            u"执行 {} 转换".format("WGS84 -> GCJ-02" if conversion_type == "WGS84_TO_GCJ02" else "GCJ-02 -> WGS84"))

        # 获取几何类型与字段结构
        desc = arcpy.Describe(input_fc)
        geometry_type = desc.shapeType
        spatial_ref = arcpy.SpatialReference(4326)

        # 创建输出图层（处理中文路径）
        out_path = os.path.dirname(output_fc)
        out_name = os.path.basename(output_fc)
        arcpy.CreateFeatureclass_management(out_path.encode('utf-8'), out_name.encode('utf-8'),
                                            geometry_type.upper(), spatial_reference=spatial_ref)

        # 添加字段（处理Unicode字段名）
        input_fields = [f for f in arcpy.ListFields(input_fc)
                        if f.type not in ("OID", "Geometry")]
        for field in input_fields:
            field_name = field.name if isinstance(field.name, str) else field.name.encode('utf-8')
            arcpy.AddField_management(output_fc.encode('utf-8'), field_name,
                                      field.type, field.precision, field.scale, field.length)

        # 字段名称列表（统一编码处理）
        field_names = [f.name.encode('utf-8') if isinstance(f.name, unicode) else str(f.name)
                       for f in input_fields]
        field_names.append("SHAPE@")

        # 使用游标处理数据
        search_cursor = None
        insert_cursor = None
        try:
            search_cursor = arcpy.da.SearchCursor(input_fc.encode('utf-8'), field_names)
            insert_cursor = arcpy.da.InsertCursor(output_fc.encode('utf-8'), field_names)

            processed_count = 0
            for row in search_cursor:
                try:
                    geom = row[-1]
                    new_geom = transform_geometry(geom, transform_func)
                    new_row = list(row[:-1]) + [new_geom]
                    insert_cursor.insertRow(new_row)
                    processed_count += 1
                    if processed_count % 1000 == 0:
                        arcpy.AddMessage(u"已处理 {} 个要素".format(processed_count))
                except Exception as e:
                    arcpy.AddWarning(u"跳过要素 {}: {}".format(processed_count, unicode(e)))
                    continue

            arcpy.AddMessage(u"成功处理 {} 个要素".format(processed_count))
        finally:
            # 确保释放游标资源
            if search_cursor:
                del search_cursor
            if insert_cursor:
                del insert_cursor

        arcpy.AddMessage(u"转换完成！输出路径: " + output_fc)

    except Exception as e:
        arcpy.AddError(u"处理失败: " + unicode(e))
        # 获取详细的错误信息
        exc_type, exc_obj, exc_tb = sys.exc_info()
        arcpy.AddError(u"错误类型: {}".format(exc_type))
        arcpy.AddError(u"错误位置: 行 {}".format(exc_tb.tb_lineno))
        raise arcpy.ExecuteError


# 主程序入口
if __name__ == "__main__":
    # 设置默认编码并运行主函数
    reload(sys)
    sys.setdefaultencoding('utf-8')
    main()