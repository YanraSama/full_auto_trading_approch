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
                info_file_start[cell] = info_file_start[cell].split("=")[0] + "=" + str(info_s[1])
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

#-------------------------------------------------------------------------------------------------------------

def find_good_folder (dossier_principal, under_folder, which_terminal = False, asset_ = ""):
    dossier_look_for  = ""

    for dossier in os.listdir(dossier_principal):
        chemin_dossier = os.path.join(dossier_principal, dossier)
        print("DANS  : ", chemin_dossier)

        if os.path.isdir(chemin_dossier):
            if which_terminal == False:
                try:
                    for sous_dossier in os.listdir(chemin_dossier):
                        chemin_fichier = os.path.join(chemin_dossier, sous_dossier)

                        if os.path.isdir(chemin_fichier):
                            if (sous_dossier == under_folder):
                                dossier_look_for = chemin_dossier.split(dossier_principal)[-1]
                                print(sous_dossier, "   ", chemin_dossier, "  -->", dossier_look_for)
                                return dossier_look_for

                except PermissionError:
                    continue

            elif os.path.exists(chemin_dossier + r"\asset.txt") == True :
                with open(chemin_dossier + r"\asset.txt") as chem:
                    for line in chem:
                        if line.strip() == asset_: 
                            with open(chemin_dossier + r"\origin.txt", "r", encoding="utf-16") as origin:
                                for path_o in origin:
                                    dossier_look_for = ( chemin_dossier.split(dossier_principal)[-1], path_o.strip() )
                                    print(dossier_look_for[0], "----", dossier_look_for[1])
                                    return dossier_look_for

    if dossier_look_for == "":
        raise ValueError("Dossier introuvable  -->", dossier_principal, " ", under_folder, "  ",  which_terminal, " ", asset_)

#-------------------------------------------------------------------------------------------------------------

def process_MT4():
    path_absolute              = r"C:\Users"
    folder_in_users            = find_good_folder(path_absolute, "full_auto_trading_approch")
    folder_in_project          = find_good_folder(path_absolute + folder_in_users, "xgboost_models")
    path_num                   = find_good_folder(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal", "tester")
    path_file_set              = path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\tester" + r"\SE.set"
    path_file_start            = path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\start.txt"
    test_asset                 = "GBPUSD"
    spread                     = "12"
    date_two_month_ago         = (date.today() - relativedelta(months=2)).strftime("%Y.%m.%d")
    date_now                   = date.today().strftime("%Y.%m.%d")
    date_two_years_ago         = (date.today() - relativedelta(months=4)).strftime("%Y.%m.%d")

    begin = date_two_years_ago
    end = date_two_month_ago

    begin_forward = date_two_month_ago
    end_forward = date_now

    print ("Temporalité : ", begin, "   ", end, "   ", begin_forward, "     ", end_forward)

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

    nbr_files         = déplacer_fichier(Path(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\tester" + r"\files"), Path(path_absolute + folder_in_users + folder_in_project + r"\xgboost_models"), "datas_models_*")
    nbr_forward_files = déplacer_fichier(Path(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\tester" + r"\files"), Path(path_absolute + folder_in_users + folder_in_project + r"\xgboost_models"), "forward_datas_*")
    opti_files        = déplacer_fichier(Path(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\tester" + r"\files"), Path(path_absolute + folder_in_users + folder_in_project + r"\xgboost_models"),f"result_optimisation_{test_asset}.csv")
    
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

        if perf_backtest > 0 and perf_forward > perf_backtest/2:
            best_set.append([x+1, perf_backtest + perf_forward])

        print ("infos perf : ", perf_backtest, "    ", seuil, "     ", best_set, "      ", perf_forward)

    if best_set:
        best_config = max(best_set, key=lambda row: row[1])
        print("BEST CONF : ", best_config[0], best_config[1])
    else:
        print("⚠️ Aucune configuration valide trouvée (aucun backtest positif ou forward insuffisant).")
        return False

    source = f"xgboost_model_v3_package_{best_config[0]}.pkl"
    final = f"xgboost_model_v3_package{test_asset}.pkl"

    os.replace(source, final)

    df = pd.read_csv(f"result_optimisation_{test_asset}.csv", sep=";", encoding="latin-1", low_memory=False)

    index_features = df.index[df['Combinaison'] == best_config[0]].tolist()

    if not index_features:
        raise ValueError("Combinaison introuvable dans le CSV")

    idx = index_features[0]

    final_set = [
        ["forward_test", "0"],
        ["live_xgboost_decision", "1"],
        ["CSV_write", "0"],
        ["Period_EEP", df["Period_EEP"].iloc[idx]],
        ["static_strat_hedge", df["static_strat_hedge"].iloc[idx]],
        ["ModeST", df["ModeST"].iloc[idx]],
        ["Mode_SS", df["Mode_SS"].iloc[idx]],
        ["Stop_Strategique", df["Stop_Strategique"].iloc[idx]],
        ["Management_Loss", df["Management_Loss"].iloc[idx]],
        ["Break_Even", df["Break_Even"].iloc[idx]],
        ["Reversal_Management", df["Reversal_Management"].iloc[idx]]
    ]

    shutil.copy2("SE.set", f"bot_{test_asset}.set")

    path_final = path_absolute + folder_in_users + folder_in_project  + r"\xgboost_models" + rf"\bot_{test_asset}.set"

    modify_text_file(path_final,  final_set, True)

    print ("FINAL SET : ", final_set)

    déplacer_fichier(Path(path_absolute + folder_in_users + folder_in_project + r"\xgboost_models"), Path(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\MQL4\Presets"), f"bot_{test_asset}.set")
    print (f"Fichier bot_{test_asset}.set prêt à ètre lancé")

    suppression(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num + r"\tester\files")
    return True
#----------------------------------------------------------------------------------------------------------------------------------------------------------

def lancement_bot(file_set, symbol):

    path_absolute              = r"C:\Users"
    folder_in_users            = find_good_folder(path_absolute, "full_auto_trading_approch")
    path_num                   = find_good_folder(path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal", "tester")
    path_file_set              = path_absolute + folder_in_users + r"\AppData\Roaming\MetaQuotes\Terminal" + path_num

    path_final = path_file_set + r"\launch.txt"

    final_set = [
        ["Symbol", symbol],
        ["ExpertParameters", file_set]
    ]

    modify_text_file(path_final,  final_set, True)

    process = subprocess.Popen([ r"C:\Program Files (x86)\FTMO Global Markets MT4 Terminal\terminal.exe","launch.txt"])
    return True


def suppression(dossier):

    for motif in ("datas_models_*", "forward_datas_*", "result_optimisation_*", "bot_*", "xgboost_model_v3_package_*"):
        for f in Path(".").glob(motif):
            f.unlink()
        for f in Path(dossier).glob(motif):
            f.unlink()


if  (process_MT4()):
  if (lancement_bot ("bot_GBPUSD.set", "GBPUSD")):
      print ("Process terminé, bot lancé")

#nbr_forward_files = déplacer_fichier(Path(r"C:\Users\rayan\AppData\Roaming\MetaQuotes\Terminal\56EE5B2C68594C11EBC44B2E705CB8B7\tester\files"), Path(r"C:\Users\rayan\Desktop\full_auto_trading_approch\xgboost_models"), "forward_datas_*")