import xml.etree.ElementTree as ET
import os

kml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "COVERAGE FTTH_24032026.kml")

def explore_kml():
    if not os.path.exists(kml_path):
        print("KML file not found!")
        return
        
    print(f"Reading KML file: {kml_path} ({os.path.getsize(kml_path)} bytes)")
    
    # Parse KML XML
    tree = ET.parse(kml_path)
    root = tree.getroot()
    
    # KML namespaces
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    # Let's count Placemarks
    placemarks = root.findall('.//kml:Placemark', ns)
    print(f"Total Placemarks found: {len(placemarks)}")
    
    # Look at the first 5 placemarks
    for i, pm in enumerate(placemarks[:5]):
        name = pm.find('kml:name', ns)
        name_text = name.text if name is not None else "No name"
        
        # Check geometries
        polygon = pm.find('.//kml:Polygon', ns)
        line = pm.find('.//kml:LineString', ns)
        point = pm.find('.//kml:Point', ns)
        
        geom_type = "Unknown"
        if polygon is not None:
            geom_type = "Polygon"
        elif line is not None:
            geom_type = "LineString"
        elif point is not None:
            geom_type = "Point"
            
        print(f"Placemark {i+1}: Name='{name_text}', Geometry={geom_type}")
        
        # If it is a polygon, let's see coordinates sample
        if polygon is not None:
            coords = polygon.find('.//kml:coordinates', ns)
            if coords is not None:
                print(f"  Coords length: {len(coords.text.strip())} characters")

if __name__ == "__main__":
    explore_kml()
