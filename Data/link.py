import json 

def group_links(): 
    sports_books = ["nike", "doxxbet", "ifortuna", "betfair", "tipsport", "tipos",]
    all_opps = []
    counter = 1
    for sb in sports_books: 
        with open("Data/" + sb + ".json", encoding="utf-8") as sb_file:
            sb_contents = sb_file.read()
            sb_data = json.loads(sb_contents)
            for obj in sb_data:
                obj["id"] = counter
                counter += 1
                all_opps.append(obj)
    return all_opps 
           
def link():
    all_opps = group_links()
    all_links = []
    triplets = [
        ["nike", 3, "doxxbet", 6, True],
        ["nike", 3, "ifortuna", 2, False],
        ["nike", 3, "tipsport", 4, False],
        ["nike", 3, "tipos", 5, False],
        ["nike", 3, "betfair", 1, False],
        ["doxxbet", 6, "ifortuna", 2, False],
        ["doxxbet", 6, "tipsport", 4, False],
        ["doxxbet", 6, "tipos", 5, False],
        ["doxxbet", 6, "betfair", 1, False],
        ["ifortuna", 2, "tipsport", 4, False],
        ["ifortuna", 2, "tipos", 5, False],
        ["ifortuna", 2, "betfair", 1, False],
        ["tipsport", 4, "tipos", 5, False],
        ["tipsport", 4, "betfair", 1, False],
        ["tipos", 5, "betfair", 1, False],
    ]
    with open("Data/link.json", encoding="utf-8") as link_file:
        link_contents = link_file.read()
        link_data = json.loads(link_contents)
        for sb1, id1, sb2, id2, write_unused in triplets: 
            sb1_data = [obj for obj in all_opps if obj["sportsbook_id"] == id1]
            sb2_data = [obj for obj in all_opps if obj["sportsbook_id"] == id2]
            sb1_data_copy = sb1_data.copy()
            for sb1_obj_copy in sb1_data_copy:
                sb1_obj = next((e for e in sb1_data if e["id"] == sb1_obj_copy["id"]), None)
                link = next((e for e in link_data[sb1 + "_" + sb2] if sb1_obj["opp_description"] == e["name1"] and sb1_obj["sport_id"] == e["sport_id"]), None)
                if link is None: continue
                sb2_obj= next((e for e in sb2_data if e["opp_description"] == link["name2"] and e["sport_id"] == link["sport_id"]), None)
                if sb2_obj is None: continue
                all_links.append({'first_opportunity_id': sb1_obj["id"], 'second_opportunity_id': sb2_obj["id"]})
                sb1_data.remove(sb1_obj)
                sb2_data.remove(sb2_obj)
            if write_unused:    
                sb1_unused = [e["opp_description"] for e in sb1_data]
                sb2_unused = [e["opp_description"] for e in sb2_data]
                with open("Data/unused_links.json", "w", encoding='utf-8') as f:
                    json.dump({"nike": sb1_unused, "doxxbet": sb2_unused}, f, ensure_ascii=False)    
    with open("Data/all_links.json", "w", encoding='utf-8') as f:
                    f.write('[\n')
                    for link in all_opps[:-1]: 
                        json.dump(link, f, ensure_ascii=False)
                        f.write(',\n')
                    json.dump(all_opps[-1], f, ensure_ascii=False)    
                    f.write('\n')
                    f.write(']\n')   
    return all_opps, all_links
                             
if __name__ == '__main__': 
    link()