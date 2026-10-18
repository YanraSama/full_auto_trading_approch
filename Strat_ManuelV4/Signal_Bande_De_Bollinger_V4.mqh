//+------------------------------------------------------------------+
//|                                    Signal_Bande_De_Bollinger.mqh |
//|                                  Copyright 2024, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#ifndef _Signal_BB_
#define _Signal_BB_

#property library
#property version "1.00"
#property strict

//-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------//---
//---                                                                                                                                                                                                         Librairy           ||
//-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------//--- 
#include <Strat_ManuelV4/Paterne_de_Continuation_V4.mqh>
#include <Strat_ManuelV4/Paterne_de_Retournement_V4.mqh>
#include <Strat_ManuelV4/Paterne_EpauleTeteEpaule_V4.mqh>
#include <Strat_ManuelV4/H4_Trend_V4.mqh>
//-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------//---
//---                                                                                                                                                                                                   Input/Global Vars        ||
//-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------//--- 
extern ushort                    BB = 20; // Period de  la BB
extern ENUM_APPLIED_PRICE BB_APLIED = PRICE_CLOSE; // MODE DE CALCUL BB
//-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------//---
//---                                                                                                                                                                                      Signal Bolingers Band Function        ||
//-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------//--- 
bool Signal_Bande_De_Bolingers(ushort IendPatern, bool Mode_H_L){

   //initialisation de la BB basse
   double LowerBB = 0.0;
   //initialisation de la BB haute
   double UpperBB = 0.0;
      
   if(BB != 0)
   {   
      for(ushort e = 1; e < IendPatern; e++)
        {
            LowerBB =iBands(symbol_opti, Period_EEP, BB, 2, 0, BB_APLIED, MODE_LOWER, e);
            UpperBB =iBands(symbol_opti, Period_EEP, BB, 2, 0, BB_APLIED, MODE_UPPER, e);

         if(Mode_H_L == true)
           {
            if(iLow(symbol_opti, Period_EEP, e) < LowerBB)
               return true;
           }
         else
            if(Mode_H_L == false)
           {
            if(iHigh(symbol_opti, Period_EEP, e) > UpperBB) 
              return true;
           }
        }
        return false;
   }
   else return true;

   return false;
}


double info_Signal_Bande_De_Bolingers(ushort IendPatern, bool Mode_H_L, double &widthBB){

   //initialisation de la BB basse
   double LowerBB = 0.0;
   //initialisation de la BB haute
   double UpperBB = 0.0;
   //initialisation de la BB du millieu
   double MidBB = 0.0;
   
   double smRatio = 0;
   double buffer_Ratio = 0;
   double Average_R = 0;
 
   double smWidth = 0;
   double buffer_width = 0;
 
   for(ushort e = 1; e < IendPatern; e++)
   {
      LowerBB =iBands(symbol_opti, Period_EEP, 20, 2, 0, BB_APLIED, MODE_LOWER, e);
      UpperBB =iBands(symbol_opti, Period_EEP, 20, 2, 0, BB_APLIED, MODE_UPPER, e);
      MidBB   =iBands(symbol_opti, Period_EEP, 20, 2, 0, BB_APLIED, MODE_MAIN, e);
         
      smRatio += (iClose(symbol_opti, Period_EEP, e)-MidBB)/(UpperBB-LowerBB);
      buffer_Ratio ++;
      
      smWidth += (UpperBB - LowerBB)/ iClose(symbol_opti, Period_EEP, e) *100;
      buffer_width ++;
   }
  Average_R = (buffer_Ratio > 0) ? smRatio/buffer_Ratio : 0;
  widthBB   = (buffer_width > 0) ? smWidth/buffer_width : 0;
  
  return Average_R;

}
   
#endif 
           