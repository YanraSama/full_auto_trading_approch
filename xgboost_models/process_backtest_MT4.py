import subprocess
import os
import time
import shutil
import random
import pandas as pd
import threading
from datetime import date
from datetime import datetime
from dateutil.relativedelta import relativedelta
import shutil
from pathlib import Path
from xgboost_learning_machine_V3 import learning_data_classifier
from backtest_models import add_signal
import numpy as np

def file_in_list(file_opti_base, info_opti_base, is_it_base_file, strip_or_no = True):
    with open(file_opti_base) as base:
        for line in base:
            line_modified = line.strip()
            if strip_or_no == False:
                line_modified = line

            if ( not (',' in line.strip()) ) and ( is_it_base_file == True ):
                info_opti_base.append([])

            if is_it_base_file == True :
                info_opti_base[-1].append(line_modified)
            
            else:
                info_opti_base.append(line_modified)


def modify_text_file(path_file_start, lists, no_take_raw_file = True):
    info_file_start = []
    verify = 0

    print("Modifie ce fichier : ", path_file_start)

    file_in_list(path_file_start, info_file_start, False, no_take_raw_file)

    for cell in range(len(info_file_start)):
        for info_s in lists:
            if ( info_file_start[cell].split("=")[0] ) == info_s[0]:
                info_file_start[cell] = info_file_start[cell].split("=")[0] + "=" + info_s[1]
                verify += 1
                print(info_file_start[cell])

    if ( verify != len(lists) ):
        raise ValueError("N'a pas modifié les dates !!!!")

    if ( os.path.exists(path_file_start) ):
        os.remove(path_file_start)

    with open(path_file_start, 'w') as start_f:
        for z in range(len(info_file_start)):
            if z < (len(info_file_start)-1) and no_take_raw_file == True:
                info_file_start[z] = info_file_start[z]+'\n'

            start_f.write(info_file_start[z])

#def optimize_MT4():

def déplacer_fichier(source, destination, file_src):
    buffer = 0
    for f in source.glob(file_src):
        if f.is_file():
            shutil.copy2(f, destination / f.name)
            print(f"Copié : {f.name}")
            buffer += 1
    return buffer

def process_MT4():
    path_file_start = r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\start.txt"
    path_file_set = r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\tester\SE.set"
    test_asset = "GBPUSD"
    spread = "12"
    date_two_month_ago = (date.today() - relativedelta(months=2)).strftime("%Y.%m.%d")
    date_now = date.today().strftime("%Y.%m.%d")
    date_two_years_ago = (date.today() - relativedelta(months=4)).strftime("%Y.%m.%d")

    begin = date_two_years_ago
    end = date_two_month_ago

    begin_forward = date_two_month_ago
    end_forward = date_now

    set_backtest = [
        ["forward_test", "0"],
        ["CSV_write", "1"]
    ]


    print("Modification du fichier SE.set pour le backtest test.")
    modify_text_file(path_file_set,  set_backtest, True)


    params = [
        ["TestFromDate", begin],
        ["TestToDate", end],
        ["TestSymbol", test_asset],
        ["TestSpread", spread]
    ]

    modify_text_file(path_file_start,  params, True)
    process = subprocess.Popen([ r"C:\Program Files (x86)\FTMO Global Markets MT4 Terminal\terminal.exe","start.txt"])
    print("MT4 lancé.\t\t")


    process.wait()      # Attendre que MT4 se termine
    print("MT4 terminé.")

    set_forward = [
        ["forward_test", "1"],
        ["CSV_write", "3"]
    ]
    print("Modification du fichier SE.set pour le forward test.")
    modify_text_file(path_file_set,  set_forward, True)

    params_forward = [
        ["TestFromDate", begin_forward],
        ["TestToDate", end_forward],
        ["TestSymbol", test_asset],
        ["TestSpread", spread]
    ]

    modify_text_file(path_file_start,  params_forward, True)
    process = subprocess.Popen([ r"C:\Program Files (x86)\FTMO Global Markets MT4 Terminal\terminal.exe","start.txt"])
    print("MT4 lancé.\t\t")


    process.wait()      
    print("MT4 terminé.")

    nbr_files         = déplacer_fichier(Path(r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\tester\files"), Path(r"C:\Users\rayan\Desktop\full_auto_trading_approch\xgboost_models"), "datas_models_*")
    nbr_forward_files = déplacer_fichier(Path(r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\tester\files"), Path(r"C:\Users\rayan\Desktop\full_auto_trading_approch\xgboost_models"), "forward_datas_*")
    opti_files        = déplacer_fichier(Path(r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\tester\files"), Path(r"C:\Users\rayan\Desktop\full_auto_trading_approch\xgboost_models"), f"result_optimisation_{test_asset}.csv")
    
    seuil = []
    best_set = []
    print ("fichiers déplacé")

    for x in range(nbr_files):
        seuil.append(learning_data_classifier(f"datas_models_{x+1}.csv", f"xgboost_model_v3_package_{x+1}.pkl")) 
        print ("SEUIL : ", seuil[x])
 
    for x in range(nbr_files):
        add_signal(f"datas_models_{x+1}.csv", f"xgboost_model_v3_package_{x+1}.pkl")

    for x in range(nbr_forward_files):
        add_signal(f"forward_datas_{x+1}.csv", f"xgboost_model_v3_package_{x+1}.pkl")

    for x in range(nbr_files):
        df = pd.read_csv(f"datas_models_{x+1}.csv", sep=";", encoding="utf-8-sig", low_memory=False)
        dt = pd.read_csv(f"forward_datas_{x+1}.csv", sep=";", encoding="utf-8-sig", low_memory=False)

        if "entry_signal" in df.columns:
            df_filtered = df[df["entry_signal"] > seuil[x]].copy()
        else:
            print("⚠️ Colonne win_rate introuvable, aucune filtration appliquée")
            df_filtered = df.copy()

        if "entry_signal" in dt.columns:
            dt_filtered = dt[dt["entry_signal"] > seuil[x]].copy()
        else:
            print("⚠️ Colonne win_rate introuvable, aucune filtration appliquée")
            dt_filtered = df.copy()

        perf_backtest = df_filtered["resultat"].sum()
        perf_forward = dt_filtered["resultat"].sum()

        #if perf_backtest > 0 and perf_forward > perf_backtest/2:
        best_set.append([x+1, perf_backtest + perf_forward])

        print ("infos perf : ", perf_backtest, "    ", seuil, "     ", best_set, "      ", perf_forward)

    if best_set:
        best_config = max(row[0] for row in best_set)
        print("BEST CONF : ", best_config)
    else:
        print("⚠️ Aucune configuration valide trouvée (aucun backtest positif ou forward insuffisant).")
        return False

    source = f"xgboost_model_v3_package_{best_config}.pkl"
    final = "xgboost_model_v3_package.pkl"

    os.rename(source, final)

    df = pd.read_csv(f"result_optimisation_{test_asset}.csv", sep=";", encoding="latin-1", low_memory=False)

    index_features = df.index[df['Combinaison'] == best_config].tolist()
    Period_EEP = df["Period_EEP"].values.astype(np.float32)
    static_strat_hedge = df["static_strat_hedge"].values.astype(np.float32)
    ModeST = df["ModeST"].values.astype(np.float32)
    Mode_SS = df["Mode_SS"].values.astype(np.float32)
    Stop_Strategique = df["Stop_Strategique"].values.astype(np.float32)
    Management_Loss = df["Management_Loss"].values.astype(np.float32)
    Break_Even = df["Break_Even"].values.astype(np.float32)
    Reversal_Management =  df["Break_Even"].values.astype(np.float32)

    final_set = [
            ["Period_EEP", Period_EEP[index_features]],
            ["static_strat_hedge", static_strat_hedge[index_features]],
            ["ModeST", ModeST[index_features]],
            ["Mode_SS", Mode_SS[index_features]],
            ["Stop_Strategique", Stop_Strategique[index_features]],
            ["Management_Loss", Management_Loss[index_features]],
            ["Break_Even", Break_Even[index_features]],
            ["Reversal_Management", Reversal_Management[index_features]]
    ]

    shutil.copy2("start.set", f"bot_{test_asset}.set")

    path_final = rf"C:\Users\rayan\Desktop\full_auto_trading_approch\xgboost_models\bot_{test_asset}.set"

    modify_text_file(path_final,  final_set, True)

    print ("FINAL SET : ", final_set)

#----------------------------------------------------------------------------------------------------------------------------------------------------------

        
process_MT4()

#nbr_forward_files = déplacer_fichier(Path(r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\tester\files"), Path(r"C:\Users\rayan\Desktop\full_auto_trading_approch\xgboost_models"), "forward_datas_*")

#for x in range(nbr_forward_files):
#    learning_data_classifier(f"forward_datas_{x+1}.csv", f"xgboost_model_v3_package_{x+1}.pkl")

#for x in range(nbr_forward_files):
#    add_signal(f"forward_datas_{x+1}.csv", f"xgboost_model_v3_package_{x+1}.pkl")