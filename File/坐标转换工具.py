import arcpy
import os
import math

# =================================================================================================================
# 坐标系转换函数（WGS84 <-> GCJ-02）
# =================================================================================================================

PI = math.pi
AXIS = 6378245.0  # 地球长轴（椭球体参数）
EE = 0.00669342162296594323  # 偏心率平方（椭球体参数）

def out_of_china(lng, lat):
    """判断坐标是否在中国以外，超出中国范围则不做加密处理"""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)

def transform_lat(x, y):
    # 计算纬度偏移量（GCJ-02算法核心部分）
    ret = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    ret += (20*math.sin(6*x*PI) + 20*math.sin(2*x*PI)) * 2/3
    ret += (20*math.sin(y*PI) + 40*math.sin(y/3*PI)) * 2/3
    ret += (160*math.sin(y/12*PI) + 320*math.sin(y*PI/30)) * 2/3
    return ret

def transform_lng(x, y):
    # 计算经度偏移量（GCJ-02算法核心部分）
    ret = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    ret += (20*math.sin(6*x*PI) + 20*math.sin(2*x*PI)) * 2/3
    ret += (20*math.sin(x*PI) + 40*math.sin(x/3*PI)) * 2/3
    ret += (150*math.sin(x/12*PI) + 300*math.sin(x/30*PI)) * 2/3
    return ret

def wgs84_to_gcj02(lng, lat):
    # WGS84坐标转GCJ-02坐标（火星坐标）
    if out_of_china(lng, lat):
        return lng, lat  # 国外不转换
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((AXIS * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (AXIS / sqrtmagic * math.cos(radlat) * PI)
    return lng + dlng, lat + dlat

def gcj02_to_wgs84(lng, lat):
    # GCJ-02坐标转WGS84坐标（近似反算）
    if out_of_china(lng, lat):
        return lng, lat
    lng2, lat2 = wgs84_to_gcj02(lng, lat)
    return lng * 2 - lng2, lat * 2 - lat2

# =================================================================================================================
# 转换几何对象（支持点/线/面）
# =================================================================================================================

def transform_geometry(geometry, transform_func):
    """应用坐标转换函数到几何对象上，支持点、线、面"""
    if geometry.type == "point":
        # 点要素直接转换
        x, y = transform_func(geometry.firstPoint.X, geometry.firstPoint.Y)
        return arcpy.PointGeometry(arcpy.Point(x, y), arcpy.SpatialReference(4326))
    elif geometry.type in ["polyline", "polygon"]:
        # 线和面要素需要遍历每个节点
        new_parts = []
        for part in geometry:
            new_part = []
            for pnt in part:
                if pnt:
                    x, y = transform_func(pnt.X, pnt.Y)
                    new_part.append(arcpy.Point(x, y))
            new_parts.append(arcpy.Array(new_part))
        if geometry.type == "polyline":
            return arcpy.Polyline(arcpy.Array(new_parts), arcpy.SpatialReference(4326))
        else:
            return arcpy.Polygon(arcpy.Array(new_parts), arcpy.SpatialReference(4326))
    else:
        raise Exception("暂不支持的几何类型：" + geometry.type)

# =================================================================================================================
# 主函数：读取输入，转换，写入输出
# =================================================================================================================

def main():
    try:
        # 参数获取（ArcGIS Pro 脚本工具传递进来）
        input_fc = arcpy.GetParameterAsText(0)     # 输入矢量图层路径
        output_fc = arcpy.GetParameterAsText(1)    # 输出矢量图层路径（shapefile）
        conversion_type = arcpy.GetParameterAsText(2)  # 选择转换方向（WGS84_TO_GCJ02 或 GCJ02_TO_WGS84）

        # 验证输入参数
        if not arcpy.Exists(input_fc):
            arcpy.AddError("输入图层不存在")
            return

        # 选择对应的转换函数
        if conversion_type == "WGS84_TO_GCJ02":
            transform_func = wgs84_to_gcj02
        elif conversion_type == "GCJ02_TO_WGS84":
            transform_func = gcj02_to_wgs84
        else:
            arcpy.AddError("无效的转换类型")
            return

        # 获取几何类型与字段结构
        desc = arcpy.Describe(input_fc)
        geometry_type = desc.shapeType
        spatial_ref = arcpy.SpatialReference(4326)  # 输出坐标系设为WGS84

        # 创建输出图层
        out_path = os.path.dirname(output_fc)
        out_name = os.path.basename(output_fc)
        arcpy.CreateFeatureclass_management(out_path, out_name, geometry_type, spatial_reference=spatial_ref)

        # 添加所有字段（除了OID、Geometry）
        input_fields = [f for f in arcpy.ListFields(input_fc) if f.type not in ("OID", "Geometry")]
        for field in input_fields:
            arcpy.AddField_management(output_fc, field.name, field.type, field.precision, field.scale, field.length)

        # 字段名称列表
        field_names = [f.name for f in input_fields]
        field_names.append("SHAPE@")  # 用于获取/写入几何对象

        # 写入数据
        with arcpy.da.SearchCursor(input_fc, field_names) as search_cursor, \
             arcpy.da.InsertCursor(output_fc, field_names) as insert_cursor:
            for row in search_cursor:
                geom = row[-1]  # 获取几何对象
                try:
                    new_geom = transform_geometry(geom, transform_func)  # 坐标转换
                    new_row = list(row[:-1]) + [new_geom]
                    insert_cursor.insertRow(new_row)  # 写入新要素
                except Exception as e:
                    arcpy.AddWarning(f"处理几何对象时出错: {str(e)}，跳过此记录")
                    continue

        arcpy.AddMessage("转换完成，新数据已保存到：" + output_fc)

    except Exception as e:
        arcpy.AddError(f"脚本执行失败: {str(e)}")
# =================================================================================================================
# 确保脚本运行时执行 main 函数
if __name__ == "__main__":
    main()
