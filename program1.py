import ezdxf
import ezdxf.bbox
from ezdxf.math import Vec2
import numpy as np
import os

def get_intersection_width(msp, y_level):
    """
    指定した高さ(y_level)において、図形と水平線の交点を求め、
    「幅（翼弦長）」と「最小のX座標（前縁位置）」を返す
    """
    intersections = []

    for entity in msp.query('LINE SPLINE LWPOLYLINE'):
        if entity.dxftype() == 'LINE':
            pts = [entity.dxf.start, entity.dxf.end]
        else:
            # 線分近似（flattening）を行う
            pts = list(entity.flattening(1.0)) 
        
        # 線分ごとの交差判定
        for i in range(len(pts) - 1):
            p1, p2 = Vec2(pts[i]), Vec2(pts[i+1])
            # y_level が線分の範囲内にあるかチェック
            if (min(p1.y, p2.y) <= y_level <= max(p1.y, p2.y)):
                if abs(p1.y - p2.y) > 1e-9: # 完全に水平な線は除外
                    x = p1.x + (p2.x - p1.x) * (y_level - p1.y) / (p2.y - p1.y)
                    intersections.append(x)
    
    # 重複する交点を削除
    if len(intersections) < 2:
        return None, None
    
    intersections = sorted(list(set(np.round(intersections, 6))))
    
    if len(intersections) < 2:
        return None, None
        
    # 小さい方のX座標を x_min、大きい方を x_max とする
    x_min, x_max = intersections[0], intersections[-1]
    chord = x_max - x_min
    
    # (幅, 最小のX座標) を返すように変更
    return chord, x_min

def process_fairing_geometry(fairing_name):
    # フォルダパス
    side_dir = "side-look"
    front_dir = "front-look"
    chord_thick_dir = "chord-&-thickness"
    pos_dir = "foil-place"

    side_input = input("側面投影図のファイル名を入力(拡張子抜き)：").strip()
    front_input = input("正面投影図のファイル名を入力(拡張子抜き)：").strip()
    
    side_path = os.path.join(side_dir, side_input + ".dxf")
    front_path = os.path.join(front_dir, front_input + ".dxf")

    try:
        doc_side = ezdxf.readfile(side_path)
        doc_front = ezdxf.readfile(front_path)
    except IOError:
        print(f"ファイルが見つかりません: {side_path} または {front_path}")
        return

    msp_side = doc_side.modelspace()
    msp_front = doc_front.modelspace()

    # --- 1. 最高点の取得 ---
    all_entities = list(msp_side.query('LINE SPLINE LWPOLYLINE'))
    y_coords = []
    for e in all_entities:
        bbox = ezdxf.bbox.extents([e])
        y_coords.append(bbox.extmax.y)
    
    y_top = max(y_coords)
    print(f"\n解析開始: 最高点 Y = {y_top:.2f} mm")

    # --- 2. 40mm刻みでの断面解析 ---
    results = []
    step = 40
    current_y = y_top

    while True:
        # 側面図から翼弦長(chord)と最小X座標(x_min)を取得
        chord, x_min_side = get_intersection_width(msp_side, current_y)
        
        # 正面図から最大厚み(thickness)を取得
        thickness_val, _ = get_intersection_width(msp_front, current_y)

        # どちらかの図面で交点が取れなくなったら終了
        if chord is None or thickness_val is None or chord < 1.0:
            if current_y == y_top: 
                current_y -= 1.0 
                continue
            break

        max_thickness_percent = (thickness_val / chord) * 100
        
        # 一列目に記録するために x_min_side を先頭に格納
        results.append([x_min_side, current_y, chord, max_thickness_percent])
        print(f"Y={current_y:7.1f} | X_min={x_min_side:7.2f} | Chord={chord:7.2f} | %={max_thickness_percent:5.2f}")
        
        current_y -= step
        if len(results) > 200: break

    # --- 3. ファイル書き出し ---
    os.makedirs(pos_dir, exist_ok=True)
    os.makedirs(chord_thick_dir, exist_ok=True)

    # foil-place への書き出し (一列目が最小X座標になる)
    pos_file_path = os.path.join(pos_dir, f"{fairing_name}_positions.txt")
    with open(pos_file_path, "w", encoding="utf-8") as f:
        for row in results:
            # 1:x_min, 2:height, 3:chord, 4:thick%
            f.write(f"{row[0]:.4f}\t{row[1]:.4f}\t{row[2]:.4f}\t{row[3]:.4f}\n")

    ct_file_path = os.path.join(chord_thick_dir, f"{fairing_name}_chord_thick.txt")
    with open(ct_file_path, "w", encoding="utf-8") as f:
        for row in results:
            f.write(f"Height: {row[1]:.1f}, Chord: {row[2]:.2f}, MaxThick%: {row[3]:.2f}\n")

    print(f"\n完了: {len(results)}個のセクションを解析しました。")

if __name__ == "__main__":
    # 実行時のデフォルト名を指定
    process_fairing_geometry("fairing-real-1")