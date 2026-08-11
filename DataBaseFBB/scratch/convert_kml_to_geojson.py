import xml.etree.ElementTree as ET
import os
import json

kml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "COVERAGE FTTH_24032026.kml")
geojson_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "coverage.geojson")

def convert_kml_to_geojson():
    if not os.path.exists(kml_path):
        print("KML file not found!")
        return False
        
    print(f"Parsing KML: {kml_path}")
    tree = ET.parse(kml_path)
    root = tree.getroot()
    
    # namespaces
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    placemarks = root.findall('.//kml:Placemark', ns)
    
    features = []
    
    for pm in placemarks:
        name_node = pm.find('kml:name', ns)
        name = name_node.text.strip() if name_node is not None else "Unnamed Area"
        
        polygon_node = pm.find('.//kml:Polygon', ns)
        if polygon_node is None:
            continue
            
        coords_node = polygon_node.find('.//kml:coordinates', ns)
        if coords_node is None:
            continue
            
        coords_text = coords_node.text.strip()
        if not coords_text:
            continue
            
        # Parse KML coordinates string: "lng,lat,alt lng,lat,alt ..." or "lng,lat lng,lat ..."
        polygon_coords = []
        # KML coords are separated by whitespace (spaces, newlines, tabs)
        points = coords_text.split()
        for pt in points:
            parts = pt.split(',')
            if len(parts) >= 2:
                try:
                    lng = float(parts[0])
                    lat = float(parts[1])
                    polygon_coords.append([lng, lat])
                except ValueError:
                    continue
                    
        if len(polygon_coords) < 3:
            continue # A polygon needs at least 3 points
            
        # Ensure the polygon is closed (first point equals last point)
        if polygon_coords[0] != polygon_coords[-1]:
            polygon_coords.append(polygon_coords[0])
            
        feature = {
            "type": "Feature",
            "properties": {
                "name": name
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon_coords]
            }
        }
        features.append(feature)
        
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    # Create static directory if it doesn't exist
    os.makedirs(os.path.dirname(geojson_path), exist_ok=True)
    
    print(f"Writing GeoJSON with {len(features)} features to: {geojson_path}")
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
        
    print("Conversion completed successfully!")
    return True

if __name__ == "__main__":
    convert_kml_to_geojson()
