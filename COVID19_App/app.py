import streamlit as st
import numpy as np, pandas as pd
from scipy.integrate import odeint
from numpy import linalg as LA
import plotly.express as px
from streamlit import caching

st.write('Este app é uma adaptação da Cappra Institute for Data Science baseada no modelo criado pela [Alison Hill](https://alhill.shinyapps.io/COVID19seir/)')

IncubPeriod = 0

#Taxa reprodutiva padrão
def taxa_reprodutiva(N, be, b0, b1, b2, b3, p1, p2, g0, g1, g2, g3, a1, u, f):
    
    return N*((be/a1)+f*(b0/g0)+(1-f)*((b1/(p1+g1))+(p1/(p1+g1))*(b2/(p2+g2)+ (p2/(p2+g2))*(b3/(u+g3)))))

#Taxa reprodutiva com sazonalidade
def taxa_reprodutiva_seas(N, be, b0, b1, b2, b3, p1, p2, g0, g1, g2, g3, a1, u, f, SeasAmp, SeasPhase):

    Ro_now = N*((b1/(p1+g1))+(p1/(p1+g1))*(b2/(p2+g2)+ (p2/(p2+g2))*(b3/(u+g3))))*(1 + SeasAmp*np.cos(2*np.pi*(0-SeasPhase)/365))
    Ro_max = N*((b1/(p1+g1))+(p1/(p1+g1))*(b2/(p2+g2)+ (p2/(p2+g2))*(b3/(u+g3))))*(1 + SeasAmp)
    Ro_min = N*((b1/(p1+g1))+(p1/(p1+g1))*(b2/(p2+g2)+ (p2/(p2+g2))*(b3/(u+g3))))*(1 - SeasAmp)
    
    return Ro_now, Ro_max, Ro_min

#Cálculo dos parâmetros do modelo SEIR            
def params(IncubPeriod, FracMild, FracCritical, FracSevere, TimeICUDeath, CFR, DurMildInf, DurHosp, i, PresymPeriod, FracAsym, DurAsym, N):
        
        if PresymPeriod > 0:
            a1 = min(10^6,1/PresymPeriod) #Frequênca de surgimento do vírus
        else:
            a1 = 10^6
         
        if IncubPeriod > PresymPeriod:
            a0 = min(10^6, 1/(IncubPeriod - PresymPeriod)) #Frequência de incubação até possibilidade de transmissão
        else:
            a0 = 10^6
        f = FracAsym #Fração de assintomáticos
        
        g0 = 1/DurAsym #Taxa de recuperação dos assintomáticos
        
        if FracCritical==0:
            u=0
        else:
            u=(1/TimeICUDeath)*(CFR/FracCritical)
            
        g1 = (1/DurMildInf)*FracMild #Taxa de recuperação I1
        p1 =(1/DurMildInf) - g1 #Taxa de progreção I1

        g3 =(1/TimeICUDeath)-u #Taxa de recuperação I3
        
        p2 =(1/DurHosp)*(FracCritical/(FracCritical+FracSevere)) #Taxa de progressão I2
        g2 = (1/DurHosp) - p2 #Taxa de recuperação de I2

        ic=np.zeros(9) #Inicia vetor da população (cada índice para cada tipo de infectado, exposto, etc)
        ic[0]= N-i #População
        ic[1] = i #População exposta
        
        return a0, a1, u, g0, g1, g2, g3, p1, p2, f, ic
#Menu dos parâmetros gerais
def menu(IncubPeriod, DurMildInf, FracSevere, FracCritical, ProbDeath, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod): #Cria o menu lateral esquerdo

        st.sidebar.subheader('Parâmetros clínicos:')
        
        FracSevere1 = int(FracSevere*100)
        FracCritical1 = int(FracCritical*100)
        ProbDeath1 = int(ProbDeath*100)
        
        #Período de incubação em dias
        IncubPeriod = st.sidebar.slider("Período de incubação (em dias)", min_value=0, max_value=20, value=IncubPeriod, step=1)  
        
        #Duração de infecções leves em dias
        DurMildInf = st.sidebar.slider("Duração de infecções leves (em dias)", min_value=1, max_value=20, value=DurMildInf, step=1) 
        
        #Fração de infecções graves
        FracSevere = st.sidebar.slider("% de infecções graves", min_value=0, max_value=100, value=FracSevere1, step=1)/100 
        
        #Duração da internação em dias
        DurHosp = st.sidebar.slider("Duração da infecção grave (permanência em leito hospitalar em dias)", min_value=1, max_value=30, value=DurHosp, step=1) 
        
        #Fração de infecções críticas
        FracCritical = st.sidebar.slider("% de infecções críticas", min_value=0, max_value=100, value=FracCritical1, step=1)/100
        
        #Duração da infecção crítica / permanência na UTI em dias
        TimeICUDeath = st.sidebar.slider("Duração da infecção crítica (permanência na UTI em dias", min_value=1, max_value=30, value=TimeICUDeath, step=1) 
        
        #Fração de infecções leves
        FracMild = 1 - FracSevere - FracCritical
        st.sidebar.text("% de infecções leves = "+str(round(FracMild*100,1))+"%")
        
        #Taxa de mortalidade de casos (fração de infecções resultando em morte)
        ProbDeath = st.sidebar.slider("Taxa de mortalidade em casos críticos", min_value=0, max_value=100, value=ProbDeath1, step=1)/100
        
        CFR = ProbDeath*FracCritical
        st.sidebar.text("Taxa de mortalidade geral = "+str(round(CFR*100,1))+"%")
        
        st.sidebar.subheader('Taxas de transmissão:')
        
        #Taxa de transmissão (infecções leves)
        b1 = st.sidebar.slider("Taxa de transmissão de infecções leves por dia", min_value=0.00, max_value=3.00, value=0.5, step=0.01) 
        
        #Taxa de transmissão (infecções graves, relativa a infecção leve)
        b2 = st.sidebar.slider("Taxa de transmissão de infecções graves por dia", min_value=0.00, max_value=3.00, value=0.1, step=0.01) 
        
        #Taxa de transmissão (infecções críticas, relativa a infecção leve)
        b3 = st.sidebar.slider("Taxa de transmissão de infecções críticas por dia", min_value=0.00, max_value=3.00, value=0.1, step=0.01) 
        
        st.sidebar.subheader('Parâmetros de infecções assintomáticas:')
        #Permitir infecções assintomáticas
        AllowAsym = st.sidebar.radio("Permitir infecções assintomáticas?", ["Não","Sim"])
        if AllowAsym=="Sim":
            #Fração de assintomáticos
            FracAsym = 0.3
            FracAsym=st.sidebar.slider("Fração de infecções assintomáticas", min_value=0, max_value=100, value=int(FracAsym*100), step=1)/100
            #Duração dos assintomáticos
            DurAsym=st.sidebar.slider("Duração de infecções assintomáticas", min_value=1, max_value=20, value=DurAsym, step=1)
            #Taxa de tranmissão
            b0 = st.sidebar.slider("Taxa de transmissão de infecções assintomáticas por dia", min_value=0.00, max_value=3.00, value=0.1, step=0.01) 
        else:
            FracAsym=0
            DurAsym=7
            b0 = 0 
        
        st.sidebar.subheader('Parâmetros de transmissões pré-sintomáticas:')
        #Permitir transmissões pré-sintomática
        AllowPresym = st.sidebar.radio("Permitir transmissões pré-sintomáticas?", ["Não","Sim"])

        if AllowPresym=="Sim":
            #Periodo de transmissão
            if IncubPeriod > 2:
                PresymPeriod=st.sidebar.slider("Tempo antes do início dos sintomas no qual a transmissão é possível", min_value=0, max_value=IncubPeriod, value=PresymPeriod, step=1)
            elif IncubPeriod == 0:
                st.sidebar.text("Periodo de incubação é zero, logo todos os expostos transmitem")
                PresymPeriod = 0
            else:
                PresymPeriod=st.sidebar.slider("Tempo antes do início dos sintomas no qual a transmissão é possível", min_value=0, max_value=IncubPeriod, value=IncubPeriod - 1, step=1)
            #Taxa de transmissão
            be = st.sidebar.slider("Taxa de transmissão pré-sintomática por dia", min_value=0.0, max_value=3.00, value=0.5, step=0.01)
        else:
            PresymPeriod=0
            be = 0
            
        st.sidebar.subheader('Parâmetros de sazonalidade:')
        #Permitir ou não a sazonalidade
        AllowSeason = st.sidebar.radio("Permitir Sazonalidade?", ["Não","Sim"])
        if AllowSeason=="Sim":
            #Amplitude da sazonlidade
            SeasAmp = st.sidebar.slider("Amplitude da sazonalidade", min_value=0, max_value=100, value=SeasAmp, step=1)/100 
            #Fase da sazonalidade
            SeasPhase = st.sidebar.slider("Amplitude da sazonalidade", min_value=-365, max_value=365, value=SeasPhase, step=1) 
        else:
            SeasAmp=0.0 
            SeasPhase=0 
        seas0=(1 + SeasAmp*np.cos(2*np.pi*SeasPhase/365)) #value of seasonality coefficient at time zero

        st.sidebar.subheader('Parâmetros da simulação:')
        #Tamanho da polulação
        N = st.sidebar.number_input(label="Tamanho da população", value=1000) 
        
        #Pessoas infectadas inicialmente
        i = st.sidebar.number_input(label="Pessoas infectadas inicialmente", value=1) 
        
        #Tempo máximo da simulação
        tmax = st.sidebar.slider("Tempo máximo da simulação em dias", min_value=0, max_value=1000, value=365, step=1)
        
        #Taxas de trnamissão percapita
        b1 = b1/(N*seas0)
        b2 = b2/(N*seas0)
        b3 = b3/(N*seas0)
        b0 = b0/(N*seas0)
        be = be/(N*seas0)
        
        return IncubPeriod, DurMildInf, FracMild, FracSevere, FracCritical, CFR, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod, seas0, b0, b1, b2, b3, be, N, i, tmax

#Menu dos parâmetros de intervenção
def intervencao(TimeStart,TimeEnd,reduc1,reduc2,reduc3,reducpre,reducasym,tmax):
        st.sidebar.subheader('Parâmetros de intervenção')
        #Início da intervenção
        TimeStart = st.sidebar.slider(label="Tempo de início da intervenção (dias)",min_value = 0, max_value = tmax, value = TimeStart, step = 1) 
        #Fim da intervenção
        TimeEnd = st.sidebar.slider(label="Tempo de fim da intervenção (dias)", min_value = 0, max_value = tmax, value = TimeEnd, step = 1) 
        #Taxa de transmissão (infecções leves)
        reduc1 = st.sidebar.slider("Redução na transmissão causada por infecções leves (%)", min_value=0, max_value=100, value=int(reduc1*100), step=1)/100   
        #Taxa de transmissão (infecções graves, relativa a infecção leve)
        reduc2 = st.sidebar.slider("Redução na transmissão causada por infecções graves (%)", min_value=0, max_value=100, value=int(reduc2*100), step=1)/100 
        #Taxa de transmissão (infecções críticas, relativa a infecção leve)
        reduc3 = st.sidebar.slider("Redução na transmissão causada por infecções críticas (%)", min_value=0, max_value=100, value=int(reduc3*100), step=1)/100
        #Redução da transmissão de assintomáticos
        reducasym = st.sidebar.slider("Redução na transmissão causada por infecções assintomáticas (%), se estiverem permitidas", min_value=0, max_value=100, value=int(reducasym*100), step = 1)/100
        #Redução da transmissão de pré-sintomáticos
        reducpre = st.sidebar.slider("Redução na transmissão causada por infecções pré sintomáticas (%), se estiverem permitidas", min_value=0, max_value=100, value=int(reducpre*100), step = 1)/100
        return TimeStart,TimeEnd,reduc1,reduc2,reduc3,reducpre, reducasym
    
#Simulação com intevenção
def simulacao(TimeStart, TimeEnd, tmax, i, N, a0, a1, b0, be, b1, b2, b3, b0Int, beInt, b1Int, b2Int, b3Int, g0, g1, g2, g3, p1, p2 , u, names, f, AllowAsym, AllowPresym, SeasAmp, SeasPhase):

    if TimeEnd>TimeStart: #Se há intervenção
            if TimeStart > 0: #Se a intervenção começa após o dia 0
                #Simulação sem intervenção (antes do início da intervenção)
                ic = np.zeros(9) #Inicia vetor da população (cada índice para cada tipo de infectado, exposto, etc)
                ic[0] = N-i #População sucetível = tamanho da população
                ic[1] = i #População exposta
                tvec = np.arange(0,TimeStart,0.1) #A simulação sem intervenção termina em t = TimeStart
                sim_sem_int_1 = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
                ic = sim_sem_int_1[-1] #Salva a população atual
                
                #Criando DataFrame
                df_sim_com_int = pd.DataFrame(sim_sem_int_1, columns = names)
                df_sim_com_int['Tempo (dias)'] = tvec
                df_sim_com_int['Simulação'] = 'Com intervenção'
            
                #Simulação após o início da intervenção
                tvec=np.arange(TimeStart,TimeEnd,0.1)
                sim_com_int = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,beInt,b0Int,b1Int,b2Int,b3Int,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
                ic = sim_com_int[-1] #Salva população atual
                #Criando DataFrame
                df_aux = pd.DataFrame(sim_com_int, columns = names)
                df_aux['Tempo (dias)'] = tvec
                df_aux['Simulação'] = 'Com intervenção'
                #Append dataframe
                df_sim_com_int = df_sim_com_int.append(df_aux)
                
                if TimeEnd < tmax: #Se a intervenção termina antes do tempo final
                    tvec = np.arange(TimeEnd,tmax,0.1) #A simulação sem intervenção termina em t = TimeStart
                    #Simulação sem intervenção (após o fim da intervenção)
                    sim_sem_int_2 = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
                    #Criando dataframe
                    df_aux = pd.DataFrame(sim_sem_int_2, columns = names)
                    df_aux['Tempo (dias)'] = tvec
                    df_aux['Simulação'] = 'Com intervenção'
                    #Append dataframe
                    df_sim_com_int = df_sim_com_int.append(df_aux)
                    
                    
            elif TimeStart == 0: #Se a intervenção começa no dia 0
                ic = np.zeros(9) #Inicia vetor da população (cada índice para cada tipo de infectado, exposto, etc)
                ic[0] = N - i #População sucetível = tamanho da população
                ic[1] = i
                tvec=np.arange(0,TimeEnd,0.1)
                sim_com_int = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,beInt,b0Int,b1Int,b2Int,b3Int,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
                ic = sim_com_int[-1]
                df_sim_com_int = pd.DataFrame(sim_com_int, columns = names)
                df_sim_com_int['Tempo (dias)'] = tvec
                df_sim_com_int['Simulação'] = 'Com intervenção'
                #sim = sim_com_int
                if TimeEnd < tmax: #Se a intervenção termina antes do tempo final
                    tvec = np.arange(TimeEnd,tmax,0.1) #A simulação sem intervenção termina em t = TimeStart
                    #Simulação sem intervenção (após o fim da intervenção)
                    sim_sem_int_2 = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
                   #Criando dataframe
                    df_aux = pd.DataFrame(sim_sem_int_2, columns = names)
                    df_aux['Tempo (dias)'] = tvec
                    df_aux['Simulação'] = 'Com intervenção'
                    df_sim_com_int = df_sim_com_int.append(df_aux)       
            return df_sim_com_int
    

#Modelo SEIR
def seir(y,t,a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase): 
        
    dy=[0, #Sucetiveis y[0]
        0, #Expostos y[1]
        0, #Expostos transmissores y[2]
        0, #I0 - Assintomáticos y[3]
        0, #I1 - Leves y[4]
        0, #I2 - Graves y[5]
        0, #I3 - Críticos y[6]
        0, #Recuperados y[7]
        0] #Mortos y[8]
    
    S = y[0] #Sucetiveis y[0]
    E0 = y[1] #Expostos y[1]
    E1 = y[2] #Expostos transmissores y[2]
    I0 = y[3] #I0 - Assintomáticos y[3]
    I1 = y[4] #I1 - Leves y[4]
    I2 = y[5] #I2 - Graves y[5]
    I3 = y[6] #I3 - Críticos y[6]
    R = y[7] #Recuperados y[7]
    D = y[8] #Mortos y[8]
    
    seas=(1 + SeasAmp*np.cos(2*np.pi*(t-SeasPhase)/365))
    
    dy[0] = -(be*E1 + b0*I0 + b1*I1 +b2*I2 + b3*I3)*S*seas #Variação de sucetíveis
    
    dy[1] = (be*E1 + b0*I0 + b1*I1 + b2*I2 + b3*I3)*S*seas - a0*E0 #Variação de expostos não transmissores
    
    if AllowPresym == 'Sim': #Se os pré-sintomáticos transmitem   
        dy[2] = a0*E0 - a1*E1 #Variação de pré-sintomáticos transmissores
        if AllowAsym == 'Sim': #Se há assintomáticos
            dy[3] = f*a1*E1 - g0*I0 #Variação de assintomáticos
            dy[4] = (1-f)*a1*E1 - g1*I1 - p1*I1 #Variação de casos leves
        else: #Se não há assintomáticos
            dy[3] = 0 #Variação de assintomáticos é zero
            dy[4] = (1-f)*a1*E1 - g1*I1 - p1*I1 #Variação de casos leves
    else: #Se os pré-sintomáticos não transmitem
        dy[2] = 0 #Variação de pré-sintomáticos transmissores é zero
        if AllowAsym == 'Sim': #Se há assintomáticos
            dy[3] = f*a0*E0 - g0*I0 #Variação de assintomáticos
            dy[4] = (1-f)*a0*E0 - g1*I1 - p1*I1 #Variação de casos leves
        else:#Se não há
            dy[3] = 0 #Variação de assintomáticos é zero
            dy[4] = (1-f)*a0*E0 - g1*I1 - p1*I1 #Variação de casos leves
 
    dy[5] = p1*I1-g2*I2-p2*I2 #Variação de casos graves
    
    dy[6] = p2*I2-g3*I3-u*I3 #Variação de casos críticos
    
    dy[7] = g0*I0+g1*I1+g2*I2+g3*I3 #Variação de recuperados
    
    dy[8] = u*I3 #Variação de mortos
    
    return dy

def new_growth_rate(g0,g1,g2,g3,p1,p2,be,b0,b1,b2,b3,u,a0,a1,N,f): #Growth rate após o update
    
    JacobianMat=np.array([
                 [-a0, N*be, N*b0, N*b1, N*b2, N*b3, 0, 0],
                 [a0, -a1, 0, 0, 0, 0, 0, 0],
                 [0, a1*f, -g0, 0, 0, 0, 0, 0],
                 [0, a1 - a1*f, 0, -p1-g1, 0, 0, 0, 0],
                 [0, 0, 0, p1, -p2-g2, 0, 0, 0],
                 [0, 0, 0, 0, p2, -u-g3, 0, 0],
                 [0, 0, g0, g1, g2, g3 , 0, 0],
                 [0, 0, 0, 0, 0, u, 0, 0]
                ])
    
    eig = LA.eig(JacobianMat)
    eigvalue = eig[0].real
    eigvector = eig[1]
    
    r = max(eigvalue)
    
    MaxEigenVector=eigvector.T[np.argmax(eigvalue)]
    MaxEigenVector=MaxEigenVector/MaxEigenVector[len(MaxEigenVector)-1]
    MaxEigenVector=MaxEigenVector.real
    DoublingTime=np.log(2)/r
    
    return r, DoublingTime


def main(IncubPeriod):
    pic = "https://images.squarespace-cdn.com/content/5c4ca9b7cef372b39c3d9aab/1575161958793-CFM6738ESA4DNTKF0SQI/CAPPRA_PRIORITARIO_BRANCO.png?content-type=image%2Fpng"
    st.sidebar.image(pic, use_column_width=False, width=100, caption=None)
    page = st.sidebar.selectbox("Simulações", ["Progressão do COVID19","Com Intervenção","Capacidade Hospitalar","Descição do Modelo","Fontes","Código"])

    if page == "Descição do Modelo":
        pic = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABjsAAAKaCAYAAABoT+uSAAAAAXNSR0IArs4c6QAAAAlwSFlzAAAXEgAAFxIBZ5/SUgAAQABJREFUeAHs3QecXFXZx/FzZpMASYCE3jukAaFEaQKhQ0RQIAGpIc2CUgRFRaqiIk0QBJIAAQSEgKK8EKqhEwRpIYWOIDUCoabunPf/rDM6zN7ZuTN7Z3bK7/l8Hmbm3nPbd1u4zz3nOEcggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAAAIJCnjta4Cyf4L7ZFcIIIAAAggggAACCCCAAAIIIIAAAggggAACCCCAQFUE1tFRnlKGTP5Dr2sqCQQQQAABBBBAAAEEEEAAAQQQQAABBBBAAAEEEECgLgQe0VlmCx3Z12lalqqLs+ckEUAAAQQQQAABBBBAAAEEEEAAAQQQQAABBBBAoKkFVtLVZwsc+a/jmlqGi0cAAQQQQAABBBBAAAEEEEAAAQQQQAABBBBAAIG6EFhWZ5lW5hc67PP7yuWVBAIIVEHAJs4hEEAAAQQQQAABBBBAAAEEEEAAAQQQQKA5BLrrMnsrl+4gl8m0sXbWvlsJafcbF2ZyQc777DJ7zV/+mZZ9EJEfatliZa3HzTrB/Qqc5EQtH1tgHYsRQCBBAYodCWKyKwQQQAABBBBAAAEEEEAAAQQQQAABBKooYIWIFZQrZtKGVCr0vq/WWYFjSWU9xSc62fxCyBwt+2devqPP1puiK2IdHXSmcqmIg9s5baN8LGIdixBAIEEBih0JYrIrBBBAAAEEEEAAAQQQQAAB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EfZR7BhhD9R0CBAgQIAAAQIECBAgQIAAAQIECBAgQKA6gaVN079YKBQvLhTixSnj2OqyDpGoLPSEmD2ZCh3/Gj4oPzb/oY3/d4iMfEDDVOwYEJskAgQIECBAgAABAgQIECBAgAABAgQIEBhJAktmN5w6KobGUIiNqUBwelqBUTjk5pdl/5u20vpJiOU1O7KuJ25of2vrITeHAQ5YsWOAcNIIECBAgAABAgQIECBAgAABAgQIECBAYGQKLLnys5OKoyacV4jZWVkonJXO4TgpnZtRHG6zTdthdYYYntt9cHpvOTy9eEXHr9MYU73j8Psodhx+z9yMCRAgQIAAAQIECBAgQIAAAQIECBAgQKAGgZaZRx8xcdLE00Ox8IWYpcJHCOlf/PxQnbnxh6G+lw4tX5cKL+vKWbYui/GFhe0dHTVMY0SHKnaM6MdrcgQIECBAgAABAgQIECBAgAABAgQIECBwIARazgl1R06bNrVQVzguForHpT2vpmYx+1w6CHxKFuKUtMBicrrv5PQSfnxfq0JSAaM7FTC2pZzOlLMlxtiZVmy8lwopm9MajU2lmG3e+eGON2584J0tB2IeI+Waih0j5UmaBwECBAgQIECAAAECBAgQIECAAAECBAgMS4GZM0PxjPDZ0XFC3Zhd5Z5ise6I7l3bO7paVofuYTlggyJAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgMBwFfh/mcR+BAoaDd4AAAAASUVORK5CYII="
        st.image(pic, use_column_width=True, caption=None)
        st.header("MODELO")
        st.write("""Utilizamos um modelo epidemiológico compartimental, baseado no modelo SEIR clássico, para descrever a disseminação e progressão clínica do COVID-19. Uma boa cartilha para esse tipo de modelo está disponível na [Wikipedia (em inglês)](https://en.wikipedia.org/wiki/Compartmental_models_in_epidemiology). É importante rastrear os diferentes resultados clínicos da infecção, uma vez que eles exigem níveis diferentes de recursos de saúde para cuidar e podem ser testados e isolados em taxas diferentes. Susceptível ($S$) indivíduos infectados começam em uma classe $E$ exposta, onde são assintomáticos e não transmitem infecção. A taxa de progressão do estágio exposto para o estágio infectado $I$, onde o indivíduo é sintomático e infeccioso, ocorre a uma taxa. As descrições clínicas dos diferentes estágios da infecção são fornecidas abaixo. Os indivíduos infectados começam com infecção leve ($I_1$), da qual eles se recuperam, na taxa $γ_1$ ou progredir para infecção grave ($I_2$), à taxa $p_1$. A infecção grave resolve na taxa $γ_2$ ou progride para um estágio crítico ($I_3$) na taxa $p_2$. Indivíduos com infecção crítica se recuperam na taxa $γ_3$ e morra na taxa $μ$. Os indivíduos recuperados são rastreados pela classe $R$ e são assumidos como protegidos contra reinfecções por toda a vida. Os indivíduos podem transmitir a infecção em qualquer estágio, embora com taxas diferentes. A taxa de transmissão no estágio $i$ é descrito por $β_i$.""")
        st.write('### Equações')
        st.latex("\dot{S} = - β_1 I_1 S_1 - β_2 I_2 S_2 - β_3 I_3 S_3")
        st.latex("\dot{E} = β_1 I_1 S_1 + β_2 I_2 S_2 + β_3 I_3 S_3 - aE")
        st.latex("\dot{I_1} = aE - γ_1 I_1 - p_1 I_1")
        st.latex("\dot{I_2} = p_1 I_1 - γ_2 I_2 - p_2 I_2")
        st.latex("\dot{I_3} = p_2 I_2 - γ_3 I_3 - p_3 I_3")
        st.latex("\dot{R} = γ_1 I_1 + γ_2 I_2 + γ_3 I_3")
        st.latex("\dot{D} = μ I_3")
        
        st.write("""### Variáveis
* $S$: Indivíduos Suscetíveis
* $E$: Indivíduos Expostos - infectados, mas ainda não infecciosos ou sintomáticos
* $I_i$: Indivíduos infectados na classe de gravidade $i$. A gravidade aumenta com $i$ e assumimos que os indivíduos devem passar por todas as classes anteriores
  * $I_1$: Infecção leve (hospitalização não é necessária) - Mild Infection
  * $I_2$: Infecção grave (hospitalização necessária) - Severe infection
  * $I_3$: Infecção crítica (cuidados na UTI necessária) - Critical infection
* $R$: Indivíduos que se recuperaram da doença e agora estão imunes
* $D$: Indivíduos mortos
* $N=S+E+I_1+I_2+I_3+R+D$ Tamanho total da população (constante)

### Parâmetros
* $βi$ taxa na qual indivíduos infectados da classe $I_i$ entram em contato com suscetíveis e os infectam
* $a$ taxa de progressão da classe exposta para a infectada
* $\gamma_i$ taxa na qual indivíduos infectados da classe $I_i$ se recuperam da doença e se tornam imunes
* $p_i$ taxa na qual indivíduos infectados da classe $I_i$ avançam para a classe $I_{I + 1}$
* $\mu$ taxa de mortalidade de indivíduos na fase mais grave da doença

### Estágios clínicos
* Infecção leve - Esses indivíduos apresentam sintomas como febre e tosse e podem apresentar pneumonia leve. A hospitalização não é necessária (embora em muitos países esses indivíduos também sejam hospitalizados)
* Infecção grave - Esses indivíduos apresentam pneumonia mais grave que causa dispnéia, frequência respiratória <30 / min, saturação sanguínea de oxigênio <93%, pressão parcial de oxigênio arterial para fração da razão inspirada de oxigênio <300 e / ou infiltrações pulmonares> 50% dentro de 24 a 48 horas. Hospitalização e oxigênio suplementar são geralmente necessários.
* Infecção crítica - Esses indivíduos apresentam insuficiência respiratória, choque séptico e / ou disfunção ou falha de múltiplos órgãos. O tratamento em uma UTI, geralmente com ventilação mecânica, é necessário.

### Relacionando observações clínicas aos parâmetros do modelo
Para determinar os parâmetros do modelo consistentes com os dados clínicos atuais, coletamos os seguintes valores a partir dos valores do controle deslizante escolhidos pelo usuário e, em seguida, usamos as fórmulas abaixo para relacioná-los aos parâmetros de taxa no modelo. Observe que as entradas do controle deslizante para intervalos de tempo são durações médias.

* IncubPeriod: período médio de incubação, dias
* DurMildInf: duração média de infecções leves, dias
* FracMild: fração média de infecções (sintomáticas) que são leves
* FracSevere: fração média de infecções (sintomáticas) graves
* FracCritical: fração média de infecções (sintomáticas) críticas
* CFR: Taxa de mortalidade de casos (fração de infecções que eventualmente resultam em morte)
* DurHosp: Duração média da hospitalização para indivíduos com infecção grave / crítica, dias
* TimeICUDeath: Tempo médio de internação na UTI até o óbito, dias

$(Nota g = γ)$""")
        
        st.code("""a=1/IncubPeriod

g1=(1/DurMildInf)*FracMild
p1=(1/DurMildInf)-g1

p2=(1/DurHosp)*(FracCritical/(FracSevere+FracCritical))
g2=(1/DurHosp)-p2

u=(1/TimeICUDeath)*(CFR/FracCritical)
g3=(1/TimeICUDeath)-u""")
        
        st.write("""
### Taxa Básica de reprodução

Ideia: $R_0$ é a soma de: 
1.  o número médio de infecções secundárias geradas de um indivíduo em estágio $I_1$
2.  a probabilidade de um indivíduo infectado progredir para $I_2$ multiplicado pelo número médio de infecções secundárias geradas a partir de um indivíduo em estágio $I_2$
3.  a probabilidade de um indivíduo infectado progredir para $I_3$ multiplicado pelo número médio de infecções secundárias geradas a partir de um indivíduo em estágio$I_3$""")

        st.latex("R_0 = N \\frac{β_1}{p_1 + γ_1} + \\frac{p_1}{p_1 + γ_1} \\begin{pmatrix}\\frac{Nβ_2}{p_2 + γ_2} + \\frac{p_2}{p_2 + γ_2}\\frac{Nβ_3}{μ + γ_3}\\end{pmatrix}")
        st.latex(" = N \\frac{β_1}{p_1 + γ_1} \\begin{pmatrix}1+\\frac{p_1}{p_2 + γ_2}\\frac{β_2}{β_1}\\begin{pmatrix}1+\\frac{p_2}{μ + γ_3}\\frac{β_3}{β_2}\\end{pmatrix}\\end{pmatrix}")
        
        st.write("""Cálculos usando a matriz de próxima geração fornecem os mesmos resultados.

### Taxa de crescimento epidêmico precoce
No início da epidemia, antes do esgotamento dos suscetíveis, a epidemia cresce a uma taxa exponencial $r$, que também pode ser descrito com o tempo de duplicação $$T_2 = \ln (2) / r$$. Durante esta fase, todas as classes infectadas crescem na mesma taxa.

### Premissas
* Este modelo é formulado como um sistema de equações diferenciais e, portanto, o resultado representa os valores esperados de cada quantidade. Ele não leva em consideração eventos estocásticos ou relata a variação esperada nas variáveis, que podem ser grandes.
* Os indivíduos devem passar por um estágio leve antes de atingir um estágio grave ou crítico
* Os indivíduos devem passar por um estágio grave antes de atingir um estágio crítico
* Somente indivíduos em um estágio crítico morrem

### Parâmetros de taxa do modelo dinâmico
Esses parâmetros podem ser alterados usando os controles deslizantes das outras guias. Os valores nesta tabela representam os valores atuais escolhidos pelos controles deslizantes. Observe que as taxas de transmissão escolhidas pelos controles deslizantes são sempre dimensionadas por $N$, de modo que $β * N$ é constante conforme $N$ alterar.""")
        parametros = pd.DataFrame({"variável":['b1*N','b2*N','b3*N','a','g1','g2','g3','p1','p2','u','N'],"valor (/dia)":[0.5,0.1,0.1,0.200,0.133,0.188,0.060,0.033,0.062,0.040,1000.000]})
        st.table(parametros)
    elif page == "Progressão do COVID19":        
        if IncubPeriod == 0:
            IncubPeriod = 5
            DurMildInf = 6
            FracSevere = 0.15
            FracCritical = 0.05
            FracMild = 1 - FracSevere - FracCritical
            ProbDeath = 0.4
            TimeICUDeath = 10
            DurHosp = 4
            tmax = 365
            i = 1
            TimeStart = 0
            TimeEnd = tmax
            AllowSeason = 'Não'
            SeasAmp = 0
            SeasPhase = 0
            AllowAsym = 'Não'
            FracAsym = 0
            DurAsym = 6
            AllowPresym = 'Não'
            PresymPeriod = 2
            
        st.title("Casos previstos de COVID-19 por resultado clínico")
        st.subheader('Simule o curso natural de uma epidemia de COVID-19 em uma única população sem nenhuma intervenção.')
        
        my_slot1 = st.empty()
        my_slot2 = st.empty()        
        my_slot3 = st.empty()
        
        #Menu
        IncubPeriod, DurMildInf, FracMild, FracSevere, FracCritical, CFR, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod, seas0, b0, b1, b2, b3, be, N, i, tmax = menu(IncubPeriod, DurMildInf, FracSevere, FracCritical, ProbDeath, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod)    

        #Parâmetros do SEIR
        a0, a1, u, g0, g1, g2, g3, p1, p2, f, ic = params(IncubPeriod, FracMild, FracCritical, FracSevere, TimeICUDeath, CFR, DurMildInf, DurHosp, i, PresymPeriod, FracAsym, DurAsym, N)
        
        #Taxa reprodutiva e valores de crescimento
        if AllowSeason:
            R0 = taxa_reprodutiva_seas(N, be, b0, b1, b2, b3, p1, p2, g0, g1, g2, g3, a1, u, f, SeasAmp, SeasPhase)[0]
        else:
            R0 = taxa_reprodutiva(N, be, b0, b1, b2, b3, p1, p2, g0, g1, g2, g3, a1, u, f)
            
        (r,DoublingTime) = new_growth_rate(g0,g1,g2,g3,p1,p2,be,b0,b1,b2,b3,u,a0,a1,N,f)
        
        my_slot2.text("R\N{SUBSCRIPT ZERO} = {0:4.1f} \nr = {1:4.1f} por dia \nt\N{SUBSCRIPT TWO} = {2:4.1f}".format(R0,r,DoublingTime))

        #Simulação
        tvec=np.arange(0,tmax,0.1)
        soln=odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))

        #Criação do dataframe
        data = []
        names = ["Sucetíveis (S)","Expostos (E0)","Pré-sintomáticos (E1)","Assintomáticos (I0)","Inf. Leve (I1)","Inf. Grave (I2)","Inf. Crítico (I3)","Recuperado (R)","Morto (D)"]
        for x in range(0, len(tvec)):
            for y in range(0, len(soln[x])):
                data.append([tvec[x],names[y],soln[x][y]])
        y_index = 'Número por ' + str(N) +' pessoas'
        df = pd.DataFrame(data,columns=['Tempo (dias)','legenda',y_index])
        
        if AllowAsym == 'Não':
            df = df[df['legenda'] != "Assintomáticos (I0)"]
        if AllowPresym == 'Não':
            df = df[df['legenda'] != "Pré-sintomáticos (E1)"]
        
        yscale = "Linear"
        def covid19_1(yscale):
            if yscale == 'Log':
                fig = px.line(df, x="Tempo (dias)", y=y_index, color='legenda', log_y=True)
            else:
                fig = px.line(df, x="Tempo (dias)", y=y_index, color='legenda')
            return my_slot1.plotly_chart(fig)
        
        yscale = my_slot3.radio("Escala do eixo Y", ["Linear", "Log"])
        covid19_1(yscale)
                        
        st.write('''**Instruções para o usuário:** O gráfico mostra o número esperado de indivíduos infectados, recuperados, suscetíveis ou mortos ao longo do tempo. Os indivíduos infectados passam primeiro por uma fase exposta / incubação, onde são assintomáticos e não infecciosos, e depois passam para um estágio sintomático e de infecções classificados pelo estado clínico da infecção (leve, grave ou crítica). Uma descrição mais detalhada do modelo é fornecida na guia Descrição do Modelo. O tamanho da população, a condição inicial e os valores dos parâmetros usados para simular a propagação da infecção podem ser especificados através dos controles deslizantes localizados no painel esquerdo. Os valores padrão do controle deslizante são iguais às estimativas extraídas da literatura (consulte a guia Fontes). Para redefinir os valores padrão, clique no botão Redefinir tudo, localizado na parte inferior do painel. O gráfico é interativo: passe o mouse sobre ele para obter valores, clique duas vezes em uma curva na legenda para isolá-la ou clique duas vezes para removê-la. Arrastar sobre um intervalo permite aplicar zoom.
        
### Variáveis
* $S$: Indivíduos Suscetíveis
* $E_0$: Indivíduos Expostos - infectados, em estágio pré-sintomático mas não transmite o vírus
* $E_1$: Indivíduos Expostos - infectados, em estágio pré-sintomático mas transmite o vírus
* $I_i$: Indivíduos infectados na classe de gravidade $i$. A gravidade aumenta com $i$ e assumimos que os indivíduos devem passar por todas as classes anteriores
  * $I_0$: Infecção assintomática (hospitalização não é necessária)
  * $I_1$: Infecção leve (hospitalização não é necessária)
  * $I_2$: Infecção grave (hospitalização necessária)
  * $I_3$: Infecção crítica (cuidados na UTI necessária)
* $R$: Indivíduos que se recuperaram da doença e agora estão imunes
* $D$: Indivíduos mortos
* $N = S + E_0 + E_1 + I+0 + I_1 + I_2 + I_3 + R + D$ Tamanho total da população (constante)

Os indivíduos $E_1$ e $I_0$ estão desativados na simulação, mas podem ser ativados no painel lateral esquerdo.''')
        
    elif page == "Com Intervenção":
        st.title('Previsão de redução do COVID-19 após adoção de medidas de intervenção como distanciamento social')
        st.subheader('Simule a mudança do avanço da epidemia de COVID-19 em uma única população com medidas de redução de transmissão (distanciamento social, quarentena, etc).')
        st.write('Os parâmetros de redução de transmissão podem ser modificados no painel lateral esquerdo.')
        if IncubPeriod == 0:
            IncubPeriod = 5
            DurMildInf = 6
            FracSevere = 0.15
            FracCritical = 0.05
            FracMild = 1 - FracSevere - FracCritical
            ProbDeath = 0.4
            TimeICUDeath = 10
            DurHosp = 4
            tmax=365
            i=1
            variable = 'I3'
            TimeStart = 0
            TimeEnd = tmax
            reduc1 = 0.3
            reduc2 = 0
            reduc3 = 0
            reducasym = 0
            reducpre = 0
            AllowSeason = 'Não'
            SeasAmp = 0
            SeasPhase = 0
            AllowAsym = 'Não'
            FracAsym = 0.3
            DurAsym = 7
            AllowPresym = 'Não'
            PresymPeriod = 2

        #Menu de interveção
        TimeStart, TimeEnd, reduc1, reduc2, reduc3, reducpre, reducasym = intervencao(TimeStart,TimeEnd,reduc1,reduc2,reduc3,reducpre,reducasym, tmax)
        
        #Menu
        IncubPeriod, DurMildInf, FracMild, FracSevere, FracCritical, CFR, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod, seas0, b0, b1, b2, b3, be, N, i, tmax = menu(IncubPeriod, DurMildInf, FracSevere, FracCritical, ProbDeath, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod)            

        names = ["Sucetíveis (S)","Expostos (E0)","Pré-sintomáticos (E1)","Assintomáticos (I0)","Inf. Leve (I1)","Inf. Grave (I2)","Inf. Crítico (I3)","Recuperado (R)","Morto (D)"]
        if AllowAsym == 'Não':
            names.remove("Assintomáticos (I0)")
        if AllowPresym == 'Não':
            names.remove("Pré-sintomáticos (E1)")

        #Menu de seleção
        st.subheader('Selecione a variável que deseja visualizar:')
        variable = st.selectbox("", names)
        
        my_slot1 = st.empty()
        my_slot2 = st.empty()        
        my_slot3 = st.empty()        
        my_slot4 = st.empty()        
        my_slot5 = st.empty()        
        my_slot6 = st.empty()        
        my_slot7 = st.empty()        
        my_slot8 = st.empty()        
        my_slot9 = st.empty()        
        my_slot10 = st.empty()
        my_slot11 = st.empty()
        my_slot12 = st.empty()
   
        #Parâmetros do SEIR
        a0, a1, u, g0, g1, g2, g3, p1, p2, f, ic = params(IncubPeriod, FracMild, FracCritical, FracSevere, TimeICUDeath, CFR, DurMildInf, DurHosp, i, PresymPeriod, FracAsym, DurAsym, N)

        #Calculo das taxas de transmissão durante a intervenção
        b1Int = (1 - reduc1)*b1
        b2Int = (1 - reduc2)*b2
        b3Int = (1 - reduc3)*b3
        beInt = (1 - reducpre)*be
        b0Int = (1 - reducasym)*b0

        tvec=np.arange(0,tmax,0.1)
        soln=odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
        
        names = ["Sucetíveis (S)","Expostos (E0)","Pré-sintomáticos (E1)","Assintomáticos (I0)","Inf. Leve (I1)","Inf. Grave (I2)","Inf. Crítico (I3)","Recuperado (R)","Morto (D)"]
#########  Simulação sem intervenção #########################################################
        tvec=np.arange(0,tmax,0.1)
        sim_sem_int = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
        #Criando dataframe
        df_sim_sem_int = pd.DataFrame(sim_sem_int, columns = names)
        df_sim_sem_int['Tempo (dias)'] = tvec
        df_sim_sem_int['Simulação'] = 'Sem intervenção'
#############################################################################################
        
        #Simulação com intervenção
        df_sim_com_int = simulacao(TimeStart, TimeEnd, tmax, i, N, a0, a1, b0, be, b1, b2 , b3, b0Int, beInt, b1Int, b2Int, b3Int, g0, g1, g2, g3, p1, p2, u, names, f, AllowAsym, AllowPresym, SeasAmp, SeasPhase)
        y_index = 'Número por ' + str(N) +' pessoas'
        df_sim_com_int = df_sim_com_int.drop_duplicates(subset = ['Tempo (dias)'], keep = 'first')
        df_sem = pd.melt(df_sim_sem_int[['Tempo (dias)',variable]], id_vars = ['Tempo (dias)'], value_name = y_index, var_name = 'Legenda')
        df_sem['Legenda'] = df_sem['Legenda'] + ' (Sem intervenção)' 
        df_com = pd.melt(df_sim_com_int[['Tempo (dias)',variable]], id_vars = ['Tempo (dias)'], value_name = y_index, var_name = 'Legenda')
        df_com['Legenda'] = df_com['Legenda'] + ' (Com intervenção)'

        #Junta dataframes
        df = df_sem.append(df_com)
        
        if AllowAsym == 'Não':
            df = df[df['Legenda'] != "Assintomáticos (I0)"]
        if AllowPresym == 'Não':
            df = df[df['Legenda'] != "Pré-sintomáticos (E1)"]
        
        yscale = "Linear"
        yscale = st.radio("Escala do eixo Y", ["Linear", "Log"])
        
        #Plot
        if yscale == 'Log':
            fig = px.line(df, x="Tempo (dias)", y=y_index, log_y=True, color = 'Legenda')
                
        else:
            fig = px.line(df, x="Tempo (dias)", y=y_index, color = 'Legenda')
        my_slot1.plotly_chart(fig)
        
        #Cálculo da taxa reprodutiva e etc    
        if AllowSeason:
            R0 = taxa_reprodutiva_seas(N, be, b0, b1, b2, b3, p1, p2, g0, g1, g2, g3, a1, u, f, SeasAmp, SeasPhase)[0]
            R0Int = taxa_reprodutiva_seas(N, beInt, b0Int, b1Int, b2Int, b3Int, p1, p2, g0, g1, g2, g3, a1, u, f, SeasAmp, SeasPhase)[0]
        else:
            R0 = taxa_reprodutiva(N, be, b0, b1, b2, b3, p1, p2, g0, g1, g2, g3, a1, u, f)
            R0 = taxa_reprodutiva(N, beInt, b0Int, b1Int, b2Int, b3Int, p1, p2, g0, g1, g2, g3, a1, u, f)

            
        (r,DoublingTime) = new_growth_rate(g0,g1,g2,g3,p1,p2,be,b0,b1,b2,b3,u,a0,a1,N,f)
        (rInt,DoublingTimeInt) = new_growth_rate(g0,g1,g2,g3,p1,p2,beInt,b0Int,b1Int,b2Int,b3Int,u,a0,a1,N,f)
        
        Stat = pd.DataFrame({'Sem intervenção':[R0,r,DoublingTime],'Com intervenção':[R0Int,rInt,DoublingTimeInt]}, index=['R\N{SUBSCRIPT ZERO}','r (por dia)','t\N{SUBSCRIPT TWO}'])
        st.table(Stat)
        st.write("**- Sem intervenção**: A taxa de crescimento epidêmico é **{0:4.2f} por dia**; o tempo de duplicação é **{1:4.1f} dias**".format(r,DoublingTime))
        st.write("**- Com intervenção**: A taxa de crescimento epidêmico é **{0:4.2f} por dia**; o tempo de duplicação é **{1:4.1f} dias**".format(rInt,DoublingTimeInt))
        
        st.write("""**Instruções para o usuário:** O gráfico mostra o número esperado de indivíduos infectados, recuperados, suscetíveis ou mortos ao longo do tempo, com e sem intervenção. Os indivíduos infectados passam primeiro por uma fase exposta / incubação, onde são assintomáticos e não infecciosos, e depois passam para um estágio sintomático e de infecções classificados pelo estado clínico da infecção (leve, grave ou crítica). Uma descrição mais detalhada do modelo é fornecida na guia Descrição do Modelo.""")
        st.write("""O tamanho da população, a condição inicial e os valores dos parâmetros usados para simular a propagação da infecção podem ser especificados através dos controles deslizantes localizados no painel esquerdo. Os valores padrão do controle deslizante são iguais às estimativas extraídas da literatura (consulte a guia Fontes). A força e o tempo da intervenção são controlados pelos controles deslizantes abaixo do gráfico. O gráfico é interativo: passe o mouse sobre ele para obter valores, clique duas vezes em uma curva na legenda para isolá-la ou clique duas vezes para removê-la. Arrastar sobre um intervalo permite aplicar zoom.""")
        
    elif page == "Capacidade Hospitalar":
        st.title('Casos COVID-19 vs capacidade de assistência médica')
        st.subheader('''Simule casos previstos do COVID-19 versus a capacidade do sistema de saúde de cuidar deles. Os cuidados necessários dependem da gravidade da doença: indivíduos com infecção "grave" requerem hospitalização e indivíduos com infecção "crítica" requerem cuidados na UTI e ventilação mecânica.''')
        st.write('Os parâmetros de redução de transmissão podem ser modificados no painel lateral esquerdo.')

        if IncubPeriod == 0:
            IncubPeriod = 5
            DurMildInf = 6
            FracSevere = 0.15
            FracCritical = 0.05
            FracMild = 1 - FracSevere - FracCritical
            ProbDeath = 0.4
            TimeICUDeath = 10
            DurHosp = 4
            tmax=365
            i=1
            variable = 'Todos casos sintomáticos (l1,l2,l3) vs Leitos de hospital e UTI'
            TimeStart = 0
            TimeEnd = tmax
            reduc1 = 0.3
            reduc2 = 0
            reduc3 = 0
            reducasym = 0
            reducpre = 0
            AllowSeason = 'Não'
            SeasAmp = 0
            SeasPhase = 0
            AllowAsym = 'Não'
            FracAsym = 0.3
            DurAsym = 7
            AllowPresym = 'Não'
            PresymPeriod = 2

        #Menu de seleção    
        varnames = ['Todos casos sintomáticos (l1,l2,l3) vs Leitos de hospital + UTI',
                 'Casos graves (l2) e críticos (l3) vs Leitos de hospital + UTI',
                 'Infecções críticas (l3) vs Leitos na UTI',
                'Infecções críticas (l3) vs Capacidade de ventilação']
        st.subheader('Selecione a variável que deseja visualizar:')
        variable = st.selectbox("", varnames)
        
        my_slot1 = st.empty()
        my_slot2 = st.empty()
        my_slot3 = st.empty()
        my_slot4 = st.empty()
        my_slot5 = st.empty()
        my_slot6 = st.empty()
        my_slot7 = st.empty()
        my_slot8 = st.empty()
        my_slot9 = st.empty()
        my_slot10 = st.empty()
        my_slot11 = st.empty()
        my_slot12 = st.empty()
        
        
        TimeStart, TimeEnd, reduc1, reduc2, reduc3, reducpre, reducasym = intervencao(TimeStart,TimeEnd,reduc1,reduc2,reduc3,reducpre,reducasym, tmax)
        
        IncubPeriod, DurMildInf, FracMild, FracSevere, FracCritical, CFR, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod, seas0, b0, b1, b2, b3, be, N, i, tmax = menu(IncubPeriod, DurMildInf, FracSevere, FracCritical, ProbDeath, DurHosp, TimeICUDeath, AllowSeason, SeasAmp, SeasPhase, AllowAsym, FracAsym, DurAsym, AllowPresym, PresymPeriod)     
           
        
        st.subheader('Capacidade do sistema de saúde')
        AvailHospBeds=st.number_input(label="Leitos hospitalares disponíveis (por mil pessoas)", value=1.95)*N/1000 #Available hospital beds per 1000 ppl in BR based on total beds and occupancy
        AvailICUBeds=st.number_input(label="Leitos na UTI disponíveis (por mil pessoas)", value=0.137)*N/1000 #Available ICU beds per 1000 ppl in BR, based on total beds and occupancy. Only counts adult not neonatal/pediatric beds
        ConvVentCap=st.number_input(label="Pacientes que podem ser ventilados em protocolos convencionais (por mil pessoas)", value=0.062)*N/1000 #Estimated excess # of patients who could be ventilated in US (per 1000 ppl) using conventional protocols
        ContVentCap=st.number_input(label="Pacientes que podem ser ventilados em protocolo de contingência (por mil pessoas)", value=0.15)*N/1000 #Estimated excess # of patients who could be ventilated in US (per 1000 ppl) using contingency protocols
        CrisisVentCap=st.number_input(label="Pacientes que podem ser ventilados em protocolo de crise (por mil pessoas)", value=0.24)*N/1000 #Estimated excess # of patients who could be ventilated in US (per 1000 ppl) using crisis protocols
       
        a0, a1, u, g0, g1, g2, g3, p1, p2, f, ic = params(IncubPeriod, FracMild, FracCritical, FracSevere, TimeICUDeath, CFR, DurMildInf, DurHosp, i, PresymPeriod, FracAsym, DurAsym, N)

        b1Int = (1 - reduc1)*b1
        b2Int = (1 - reduc2)*b2
        b3Int = (1 - reduc3)*b3
        beInt = max(0,(1 - reducpre)*be)
        b0Int = max(0,(1 - reducasym)*b0) 
        
        names = ["Sucetíveis (S)","Expostos (E1)","Pré-sintomáticos (E1)","Assintomáticos (I0)","Inf. Leve (I1)","Inf. Grave (I2)","Inf. Crítico (I3)","Recuperado (R)","Morto (D)"]

#########  Simulação sem intervenção #########################################################
        tvec=np.arange(0,tmax,0.1)
        sim_sem_int = odeint(seir,ic,tvec,args=(a0,a1,g0,g1,g2,g3,p1,p2,u,be,b0,b1,b2,b3,f, AllowPresym, AllowAsym, SeasAmp, SeasPhase))
        #Criando dataframe
        df_sim_sem_int = pd.DataFrame(sim_sem_int, columns = names)
        df_sim_sem_int['Tempo (dias)'] = tvec
        df_sim_sem_int['Simulação'] = 'Sem intervenção'
#############################################################################################
        
        #Simulação com intervenção
        df_sim_com_int = simulacao(TimeStart, TimeEnd, tmax, i, N, a0, a1, b0, be, b1, b2 , b3, b0Int, beInt, b1Int, b2Int, b3Int, g0, g1, g2, g3, p1, p2, u, names, f, AllowAsym, AllowPresym, SeasAmp, SeasPhase)
        y_index = 'Número por ' + str(N) +' pessoas'  

        #Plots
        if variable == 'Todos casos sintomáticos (l1,l2,l3) vs Leitos de hospital + UTI':
            df_sim_com_int[y_index] = df_sim_com_int["Inf. Leve (I1)"] + df_sim_com_int["Inf. Grave (I2)"] + df_sim_com_int["Inf. Crítico (I3)"]
            df_sim_sem_int[y_index] = df_sim_sem_int["Inf. Leve (I1)"] + df_sim_sem_int["Inf. Grave (I2)"] + df_sim_sem_int["Inf. Crítico (I3)"]
            df = df_sim_sem_int[['Tempo (dias)',y_index, 'Simulação']].append(df_sim_com_int[['Tempo (dias)',y_index, 'Simulação']])
            
            data1 = []
            for x in range(0, tmax):
                data1.append([x,'Leitos hospitalares + UTI',AvailHospBeds + AvailICUBeds])
                
            df = df.append(pd.DataFrame(data1, columns = ['Tempo (dias)','Simulação',y_index]))
            
        elif variable == 'Casos graves (l2) e críticos (l3) vs Leitos de hospital + UTI':
            df_sim_com_int[y_index] = df_sim_com_int["Inf. Grave (I2)"] + df_sim_com_int["Inf. Crítico (I3)"]
            df_sim_sem_int[y_index] = df_sim_sem_int["Inf. Grave (I2)"] + df_sim_sem_int["Inf. Crítico (I3)"]
            df = df_sim_sem_int[['Tempo (dias)',y_index, 'Simulação']].append(df_sim_com_int[['Tempo (dias)',y_index, 'Simulação']])
            
            data1 = []
            for x in range(0, tmax):
                data1.append([x,'Leitos hospitalares + UTI',AvailHospBeds + AvailICUBeds])
                
            df = df.append(pd.DataFrame(data1, columns = ['Tempo (dias)','Simulação',y_index]))

        elif variable == 'Infecções críticas (l3) vs Leitos na UTI':
            df_sim_com_int[y_index] = df_sim_com_int["Inf. Crítico (I3)"]
            df_sim_sem_int[y_index] = df_sim_sem_int["Inf. Crítico (I3)"]
            df = df_sim_sem_int[['Tempo (dias)',y_index, 'Simulação']].append(df_sim_com_int[['Tempo (dias)',y_index, 'Simulação']])
            
            data1 = []
            for x in range(0, tmax):
                data1.append([x,'Leitos da UTI',AvailICUBeds])
                
            df = df.append(pd.DataFrame(data1, columns = ['Tempo (dias)','Simulação',y_index]))
        
        elif variable == 'Infecções críticas (l3) vs Capacidade de ventilação':
            df_sim_com_int[y_index] = df_sim_com_int["Inf. Crítico (I3)"]
            df_sim_sem_int[y_index] = df_sim_sem_int["Inf. Crítico (I3)"]
            df = df_sim_sem_int[['Tempo (dias)',y_index, 'Simulação']].append(df_sim_com_int[['Tempo (dias)',y_index, 'Simulação']])
            
            data1 = []
            data2 = []
            data3 = []
            for x in range(0, tmax):
                data1.append([x,'Ventilação em protocolos convencionais',ConvVentCap])
                data2.append([x,'Ventilação em protocolo de convenção',ContVentCap])
                data3.append([x,'Ventilação em protocolo de crise',CrisisVentCap])
                
            df = df.append(pd.DataFrame(data1, columns = ['Tempo (dias)','Simulação',y_index]))
            df = df.append(pd.DataFrame(data2, columns = ['Tempo (dias)','Simulação',y_index]))
            df = df.append(pd.DataFrame(data3, columns = ['Tempo (dias)','Simulação',y_index]))
            
        fig = px.line(df, x="Tempo (dias)", y=y_index, color = 'Simulação')
        my_slot1.plotly_chart(fig)

        
        st.write("""**Instruções para o usuário:** O gráfico mostra o número esperado de indivíduos infectados, recuperados, suscetíveis ou mortos ao longo do tempo, com e sem intervenção. Os indivíduos infectados passam primeiro por uma fase exposta / incubação, onde são assintomáticos e não infecciosos, e depois passam para um estágio sintomático e de infecções classificados pelo estado clínico da infecção (leve, grave ou crítica). Uma descrição mais detalhada do modelo é fornecida na guia Descrição do Modelo.""")
        st.write("""O tamanho da população, a condição inicial e os valores dos parâmetros usados para simular a propagação da infecção podem ser especificados através dos controles deslizantes localizados no painel esquerdo. Os valores padrão do controle deslizante são iguais às estimativas extraídas da literatura (consulte a guia Fontes). A força e o tempo da intervenção são controlados pelos controles deslizantes abaixo do gráfico. O gráfico é interativo: passe o mouse sobre ele para obter valores, clique duas vezes em uma curva na legenda para isolá-la ou clique duas vezes para removê-la. Arrastar sobre um intervalo permite aplicar zoom.""")
        
    elif page=="Fontes":
        st.write("""## Descrição e fontes para parâmetros de simulação
#### Estrutura do modelo
A estrutura básica do modelo é inspirada em muitos estudos sobre a progressão clínica natural da infecção por COVID-19. Para um bom resumo, consulte (Wu e McGoogan 2020). Os indivíduos infectados não desenvolvem sintomas graves imediatamente, mas passam primeiro pelas fases mais leves da infecção. Em alguns estudos, o que chamamos de infecções _leves_ são agrupadas em duas categorias diferentes, _leve_ e _moderada_, em que indivíduos com infecção _moderada_ apresentam sinais radiográficos de pneumonia leve. Esses casos _leves_ e _moderados_ ocorrem em proporções aproximadamente iguais (por exemplo, ver P. Yang et al. (2020)). Há algum debate sobre o papel da transmissão pré-sintomática (que ocorre no estágio exposto) e a infecção e transmissão assintomáticas do COVID-19. A versão atual do modelo não inclui esses efeitos.

#### Parâmetros do modelo dinâmico
O comportamento do modelo dinâmico é determinado por um conjunto de parâmetros de taxa, incluindo as taxas de transmissão $β_i$, a progressão classifica um e $p_i$, as taxas de recuperação $γ_i$ e a taxa de mortalidade $μ$. Embora essas taxas em si geralmente não sejam medidas diretamente nos estudos, outras quantidades mensuráveis podem ser usadas para recuperar esses parâmetros de taxa.

O tempo gasto na classe exposta é chamado de _período de incubação_ e geralmente é considerado igual ao tempo entre a exposição a uma fonte infectada e o desenvolvimento de sintomas. No modelo, o período médio de incubação é de $1 / a$.

O período infeccioso é o tempo durante o qual um indivíduo pode transmitir a outros. Em nosso modelo, há potencialmente três períodos infecciosos diferentes, ocorrendo durante cada estágio clínico da infecção ($I_1$,$I_2$,$I_3$) Precisamos saber a duração de cada uma dessas etapas. Acreditamos que é provável que um indivíduo seja mais infeccioso durante o estágio de infecção leve, quando ainda estaria na comunidade e se sentindo bem o suficiente para interagir com outros, mas no modelo também há a opção de transmissão nos outros estágios, por exemplo, transmissão de pacientes hospitalizados para seus profissionais de saúde. Em nível populacional, esperamos que a maior parte da transmissão ocorra a partir desses indivíduos com infecção leve, uma vez que a maioria dos pacientes não progride além desse estágio. Para o COVID-19, podemos estimar a duração do primeiro estágio de
a) a duração dos sintomas leves, b) o tempo desde o início dos sintomas até a hospitalização (por exemplo, progresso para o estágio grave) ou c) a duração do derramamento viral por escarro ou esfregaços na garganta, d) o intervalo serial entre o início dos sintomas em um caso índice e um caso secundário que eles infectam. No modelo, as quantidades a) -c) são iguais a $1 / (p_1 + γ_1)$, enquanto d) é $1 / a + (1/2) 1 / (p_1 + γ_1)$. Essas estimativas convergem em valores semelhantes para $p_1 + γ_1$. A probabilidade de progredir para o estágio grave é igual à proporção de todas as infecções que acabam sendo graves ou críticas e deve ser igual à combinação de parâmetros $p_1 / (p_1 + γ_1)$.

Indivíduos com infecção grave ($I_2$) requerem hospitalização. A duração das infecções graves, que podem ser relatadas como o tempo entre a internação e a recuperação de indivíduos que não progrediram para o estágio crítico, ou o tempo entre a internação e a internação na UTI (uma vez que casos críticos requerem cuidados no nível da UTI), para os parâmetros do modelo $1 / (p_2 + γ_2)$. Como não existem estimativas diretas dessa duração, utilizamos estimativas do tempo total desde o início dos sintomas até a admissão na UTI (por exemplo, duração combinada de infecção leve + grave) e subtraímos a duração inferida da infecção leve. Em seguida, usamos a probabilidade observada de progredir para infecção crítica, igual à proporção de infecções críticas para críticas + graves, que é igual a $p_2 / (p_2 + γ_2)$, para resolver separadamente $p_2$ e $γ_2$. No estágio crítico da infecção ($I_3$) Cuidados na UTI, geralmente com ventilação mecânica, são necessários. A duração deste estágio da infecção, p. o tempo entre a admissão na UTI e a recuperação ou morte é igual a $1 / (γ_3 + μ)$, mas nem sempre são relatados. Em vez disso, os estudos geralmente relatam o tempo total desde a internação até a morte, o que pode aproximar a soma da duração dos estágios grave e crítico. Assim, subtraindo a duração de $I_2$, a duração de $I_3$ pode ser estimado. A taxa de fatalidade de casos observados (CFR) descreve a fração de todos os indivíduos infectados sintomáticos que eventualmente morrem. Como os indivíduos precisam progredir para a infecção crítica para morrer, a probabilidade condicional de alguém na fase crítica morrer ou se recuperar é dada pelo CFR dividido pela fração de todas as infecções graves. Isso deve ser igual à combinação de parâmetros do modelo $μ / (γ_3 + μ)$.

A Tabela 1 resume as fontes de literatura que usamos para estimar os valores padrão para todos esses parâmetros do modelo. Os usuários podem escolher seus próprios valores com base em outros estudos ou contextos regionais específicos.""")
        
        data = [{'Quantidade': 'Período de incubação',
  'Parâmetro': '1/a',
  'Valor': '5 dias',
  'Fonte': '(Li et al. 2020 ; Linton et al. 2020; Lauer et al. 2020; Bi et al. 2020; Sanche et al. 2020)'},
 {'Quantidade': 'Proporção de infecções leves',
  'Parâmetro': 'γ1/(p1+γ1)',
  'Valor': '81%',
  'Fonte': '(Wu and McGoogan 2020; P. Yang et al. 2020; Liu et al. 2020)'},
 {'Quantidade': 'Duração de infecções leves',
  'Parâmetro': '1/(p1+γ1)',
  'Valor': '6 dias',
  'Fonte': 'Viral shedding: (Woelfel et al. 2020), Time from symptoms to hospitalization: (Sanche et al. 2020; Tindale et al. 2020)'},
 {'Quantidade': 'Proporção de infecções graves',
  'Parâmetro': 'γ1/(p1+γ1)',
  'Valor': '14%',
  'Fonte': '(Wu and McGoogan 2020; P. Yang et al. 2020)'},
 {'Quantidade': 'Tempo desde os sintomas até a internação na UTI',
  'Parâmetro': '-',
  'Valor': '10 dias',
  'Fonte': '(Huang et al. 2020; X. Yang et al. 2020; Liu et al. 2020)'},
 {'Quantidade': 'Duração da infecção grave',
  'Parâmetro': '1/(p2+γ2)',
  'Valor': '4 dias',
  'Fonte': '[Time from symptoms to ICU admit] - [Duration of mild infections]'},
 {'Quantidade': 'Proporção de infecções críticas',
  'Parâmetro': '% Severe\n×p2/(p2+γ2)',
  'Valor': '6%',
  'Fonte': '(Wu and McGoogan 2020; P. Yang et al. 2020; Liu et al. 2020)'},
 {'Quantidade': 'Tempo desde a internação até a morte',
  'Parâmetro': '-',
  'Valor': '14 dias',
  'Fonte': '(Sanche et al. 2020; Linton et al. 2020)'},
 {'Quantidade': 'Durante uma infecção crítica',
  'Parâmetro': '1/(μ+γ3)',
  'Valor': '10 dias',
  'Fonte': '[Time from hospital admit to death] - [Duration of severe infections]'},
 {'Quantidade': 'Razão de fatalidade de casos',
  'Parâmetro': '% Critical\n×μ/(μ+γ3)',
  'Valor': '2%',
  'Fonte': '(Wu and McGoogan 2020; Russell 2020; Riou et al. 2020; Baud et al. 2020)'}]
        df_param = pd.DataFrame(data)
        st.table(df_param)
        
        st.text('Tabela 1: Parâmetros estimados para progressão clínica do COVID-19 e fontes da literatura')
        st.write("""As taxas de transmissão são geralmente impossíveis de observar ou estimar diretamente. Em vez disso, esses valores podem ser recuperados observando a taxa de crescimento exponencial inicial ($r$) de uma epidemia e escolhendo taxas de transmissão que recriam essas observações. O crescimento dos surtos de COVID-19 variou muito entre as configurações e ao longo do tempo. Alguns valores relatados na literatura estão na Tabela 2. O cálculo automatizado em tempo real das taxas de crescimento para diferentes países está disponível no [CITE]. Os valores padrão para a simulação estão atualmente configurados para corresponder a uma situação com $r$ = [ADDDD]. Como padrão, assumimos que apenas $β1> 0$
  (por exemplo, sem transmissão hospitalar).""")
        
        data1=[{'Taxa de contagio r': 0.1,
  'Tempo de duplicação': 6.9,
  'Localização': 'Wuhan',
  'Datas': 'Early January',
  'Fonte': '(Li et al. 2020)'},
 {'Taxa de contagio r': 0.25,
  'Tempo de duplicação': 2.8,
  'Localização': 'Wuhan',
  'Datas': 'January',
  'Fonte': '(Zhao, Chen, and Small 2020)'},
 {'Taxa de contagio r': 0.3,
  'Tempo de duplicação': 2.3,
  'Localização': 'Wuhan',
  'Datas': 'January',
  'Fonte': '(Sanche et al. 2020)'},
 {'Taxa de contagio r': 0.5,
  'Tempo de duplicação': 1.4,
  'Localização': 'Itália',
  'Datas': '24 de Fev',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.17,
  'Tempo de duplicação': 4.1,
  'Localização': 'Itália',
  'Datas': '9 de Mar',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.3,
  'Tempo de duplicação': 2.3,
  'Localização': 'Irã',
  'Datas': '2 de Mar',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.5,
  'Tempo de duplicação': 1.4,
  'Localização': 'Espanha',
  'Datas': '29 de Fev',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.2,
  'Tempo de duplicação': 3.5,
  'Localização': 'Espanha',
  'Datas': '9 de Mar',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.2,
  'Tempo de duplicação': 3.5,
  'Localização': 'França',
  'Datas': '9 de Mar',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.2,
  'Tempo de duplicação': 3.5,
  'Localização': 'Coréia do Sul',
  'Datas': '24 de Fev',
  'Fonte': '(Abbott 2020)'},
 {'Taxa de contagio r': 0.5,
  'Tempo de duplicação': 1.4,
  'Localização': 'Reino Unido',
  'Datas': '2 de Mar',
  'Fonte': '(Abbott 2020)'}]
        
        df_tax = pd.DataFrame(data1)
        st.table(df_tax)
        
        st.text('Tabela 2: Taxas de crescimento precoce da epidemia observadas $r$ em diferentes configurações, juntamente com os tempos de duplicação correspondentes. Existem muitas outras configurações nas quais as taxas de crescimento agora estão próximas de zero.')
        
        st.write("""#### Parâmetros de capacidade do hospital
Um dos maiores perigos de uma epidemia generalizada de COVID-19 é a tensão que isso poderia causar aos recursos hospitalares, uma vez que indivíduos com infecção grave e crítica requerem cuidados hospitalares. O estágio crítico da infecção requer ventilação mecânica, que é o nível de cuidados na UTI. A infecção grave pode ser tratada em uma enfermaria hospitalar regular. Indivíduos com infecção leve não necessitam de hospitalização e podem se recuperar em casa sozinhos. No entanto, em muitos países, esses indivíduos também foram hospitalizados, provavelmente como uma maneira de isolá-los e reduzir a transmissão, além de monitorá-los quanto à progressão para estágios mais agressivos da doença.

Os parâmetros padrão de capacidade hospitalar são estimados para os EUA e expressos como recursos per capita. Os leitos hospitalares disponíveis (em enfermarias regulares ou no piso da UTI) dependem do número total de leitos existentes e do nível de ocupação. Durante a temporada de gripe (meses de inverno), os níveis de ocupação são geralmente mais altos. Relatamos o número de camas _disponíveis_ (por exemplo, desocupadas) de ambos os tipos (Tabela 3). Estudos na literatura de preparação para pandemia examinaram como a capacidade de fornecer ventilação mecânica durante um surto de patógeno respiratório poderia ser expandida além da capacidade tradicional do leito de UTI (também conhecida como _capacidade convencional_) usando ventiladores armazenados em estoque, equipe hospitalar não especializada e adaptação retroativa outros quartos de hospital (Ajao et al. 2015). Esses níveis de entrega expandidos são chamados de capacidade de _contingência_ e _crise_.""")
        
        data2=[{'Quantidade r': 'Leitos hospitalares',
  'Total': '900.000',
  'Por 1.000 pessoas': '2.8',
  'País': 'EUA',
  'Fonte': '(National Center for Health Statistics 2017)'},
 {'Quantidade r': 'Occupação',
  'Total': '66%',
  'Por 1.000 pessoas': '',
  'País': 'EUA',
  'Fonte': '(National Center for Health Statistics 2017)'},
 {'Quantidade r': 'Leitos de UTI',
  'Total': '80.000',
  'Por 1.000 pessoas': '0.26',
  'País': 'EUA',
  'Fonte': '(Critical Care Medicine (SCCM) 2010)'},
 {'Quantidade r': 'Ocupação',
  'Total': '68%',
  'Por 1.000 pessoas': '',
  'País': 'EUA',
  'Fonte': '(Critical Care Medicine (SCCM) 2010)'},
 {'Quantidade r': 'Aumento durante a temporada de gripe',
  'Total': '7%',
  'Por 1.000 pessoas': '',
  'País': 'EUA',
  'Fonte': '(Ajao et al. 2015)'},
 {'Quantidade r': 'Leitos hospitalares disponíveis',
  'Total': '264.000',
  'Por 1.000 pessoas': '0.82',
  'País': 'EUA',
  'Fonte': 'From above'},
 {'Quantidade r': 'Leitos de UTI disponíveis',
  'Total': '22.000',
  'Por 1.000 pessoas': '0.071',
  'País': 'EUA',
  'Fonte': 'From above'},
 {'Quantidade r': 'Capacidade de ventilação mecânica convencional',
  'Total': '20.000',
  'Por 1.000 pessoas': '0.062',
  'País': 'EUA',
  'Fonte': '(Ajao et al. 2015)'},
 {'Quantidade r': 'Capacidade de ventilação mecânica de contingência',
  'Total': '50.000',
  'Por 1.000 pessoas': '0.15',
  'País': 'EUA',
  'Fonte': '(Ajao et al. 2015)'},
 {'Quantidade r': 'Capacidade de ventilação mecânica crítica',
  'Total': '135.000',
  'Por 1.000 pessoas': '0.24',
  'País': 'EUA',
  'Fonte': '(Ajao et al. 2015)'}]
        df_capa_US = pd.DataFrame(data2)
        st.table(df_capa_US)
        
        data3=[{'Quantidade r': 'Leitos hospitalares',
  'Total': '426.388',
  'Por 1.000 pessoas': '1.95',
  'País': 'BR',
  'Fonte': '(Data SUS 2020)'},
 {'Quantidade r': 'Occupação',
  'Total': '75%',
  'Por 1.000 pessoas': '',
  'País': 'BR',
  'Fonte': '(ANS 2012)'},
 {'Quantidade r': 'Leitos de UTI',
  'Total': '41.741 Totais\n28.638 Adultos',
  'Por 1.000 pessoas': '0.137',
  'País': 'BR',
  'Fonte': '(PEBMed 2018)'},
 {'Quantidade r': 'Ocupação',
  'Total': '75%',
  'Por 1.000 pessoas': '',
  'País': 'BR',
  'Fonte': '(ANS 2012)'},
 {'Quantidade r': 'Aumento durante a temporada de gripe',
  'Total': '10%',
  'Por 1.000 pessoas': '',
  'País': 'BR',
  'Fonte': '(ANS 2012)'}]
        df_capa_BR = pd.DataFrame(data3)
        st.table(df_capa_BR)
        
        st.text('Tabela 3. Capacidade hospitalar. Os valores são apenas para camas de adultos.')
        
        st.write("""### Referências
        
**Parâmetros Brasil:**

Federação Brasileira de Hospitais. 2019. "Cenário dos Hospitais Brasileiros 2019" http://fbh.com.br/wp-content/uploads/2019/05/CenarioDosHospitaisNoBrasil2019_10maio2019_web.pdf
Data SUS. 2020. "CNES - RECURSOS FÍSICOS - HOSPITALAR - LEITOS DE INTERNAÇÃO - BRASIL" http://tabnet.datasus.gov.br/cgi/deftohtm.exe?cnes/cnv/leiintbr.def
Portal PEDMed. 2018. "Brasil tem 2 leitos de UTI para cada 10 mil habitantes" https://pebmed.com.br/brasil-tem-2-leitos-de-uti-para-cada-10-mil-habitantes/
ANS. 2012. "Taxa de Ocupação Operacional Geral" http://www.ans.gov.br/images/stories/prestadores/E-EFI-01.pdf

**Simulador, parâmetros e modelo:**

Abbott, Sam. 2020. “Temporal Variation in Transmission During the COVID-19 Outbreak.” CMMID Repository. https://cmmid.github.io/topics/covid19/current-patterns-transmission/global-time-varying-transmission.html.

Ajao, Adebola, Scott V. Nystrom, Lisa M. Koonin, Anita Patel, David R. Howell, Prasith Baccam, Tim Lant, Eileen Malatino, Margaret Chamberlin, and Martin I. Meltzer. 2015. “Assessing the Capacity of the Healthcare System to Use Additional Mechanical Ventilators During a Large-Scale Public Health Emergency (PHE).” Disaster Medicine and Public Health Preparedness 9 (6): 634–41. https://doi.org/10.1017/dmp.2015.105.

Baud, David, Xiaolong Qi, Karin Nielsen-Saines, Didier Musso, Leo Pomar, and Guillaume Favre. 2020. “Real Estimates of Mortality Following COVID-19 Infection.” The Lancet Infectious Diseases 0 (0). https://doi.org/10.1016/S1473-3099(20)30195-X.

Bi, Qifang, Yongsheng Wu, Shujiang Mei, Chenfei Ye, Xuan Zou, Zhen Zhang, Xiaojian Liu, et al. 2020. “Epidemiology and Transmission of COVID-19 in Shenzhen China: Analysis of 391 Cases and 1,286 of Their Close Contacts.” medRxiv, March, 2020.03.03.20028423. https://doi.org/10.1101/2020.03.03.20028423.

Critical Care Medicine (SCCM), Society of. 2010. “SCCM Critical Care Statistics.” https://sccm.org/Communications/Critical-Care-Statistics.

Huang, Chaolin, Yeming Wang, Xingwang Li, Lili Ren, Jianping Zhao, Yi Hu, Li Zhang, et al. 2020. “Clinical Features of Patients Infected with 2019 Novel Coronavirus in Wuhan, China.” The Lancet 395 (10223): 497–506. https://doi.org/10.1016/S0140-6736(20)30183-5.

Lauer, Stephen A., Kyra H. Grantz, Qifang Bi, Forrest K. Jones, Qulu Zheng, Hannah Meredith, Andrew S. Azman, Nicholas G. Reich, and Justin Lessler. 2020. “The Incubation Period of 2019-nCoV from Publicly Reported Confirmed Cases: Estimation and Application.” medRxiv, February, 2020.02.02.20020016. https://doi.org/10.1101/2020.02.02.20020016.

Li, Qun, Xuhua Guan, Peng Wu, Xiaoye Wang, Lei Zhou, Yeqing Tong, Ruiqi Ren, et al. 2020. “Early Transmission Dynamics in Wuhan, China, of Novel Coronavirus-Infected Pneumonia.” New England Journal of Medicine 0 (0): null. https://doi.org/10.1056/NEJMoa2001316.

Linton, Natalie M., Tetsuro Kobayashi, Yichi Yang, Katsuma Hayashi, Andrei R. Akhmetzhanov, Sung-mok Jung, Baoyin Yuan, Ryo Kinoshita, and Hiroshi Nishiura. 2020. “Incubation Period and Other Epidemiological Characteristics of 2019 Novel Coronavirus Infections with Right Truncation: A Statistical Analysis of Publicly Available Case Data.” Journal of Clinical Medicine 9 (2): 538. https://doi.org/10.3390/jcm9020538.

Liu, Jingyuan, Yao Liu, Pan Xiang, Lin Pu, Haofeng Xiong, Chuansheng Li, Ming Zhang, et al. 2020. “Neutrophil-to-Lymphocyte Ratio Predicts Severe Illness Patients with 2019 Novel Coronavirus in the Early Stage.” medRxiv, February, 2020.02.10.20021584. https://doi.org/10.1101/2020.02.10.20021584.

National Center for Health Statistics. 2017. “Table 89. Hospitals, Beds, and Occupancy Rates, by Type of Ownership and Size of Hospital: United States, Selected Years 1975-2015.”

Riou, Julien, Anthony Hauser, Michel J. Counotte, and Christian L. Althaus. 2020. “Adjusted Age-Specific Case Fatality Ratio During the COVID-19 Epidemic in Hubei, China, January and February 2020.” medRxiv, March. https://doi.org/10.1101/2020.03.04.20031104.

Russell, Timothy W. 2020. “Estimating the Infection and Case Fatality Ratio for COVID-19 Using Age-Adjusted Data from the Outbreak on the Diamond Princess Cruise Ship.” CMMID Repository. https://cmmid.github.io/topics/covid19/severity/diamond_cruise_cfr_estimates.html.

Sanche, Steven, Yen Ting Lin, Chonggang Xu, Ethan Romero-Severson, Nick Hengartner, and Ruian Ke. 2020. “The Novel Coronavirus, 2019-nCoV, Is Highly Contagious and More Infectious Than Initially Estimated.” medRxiv, February, 2020.02.07.20021154. https://doi.org/10.1101/2020.02.07.20021154.

Tindale, Lauren, Michelle Coombe, Jessica E. Stockdale, Emma Garlock, Wing Yin Venus Lau, Manu Saraswat, Yen-Hsiang Brian Lee, et al. 2020. “Transmission Interval Estimates Suggest Pre-Symptomatic Spread of COVID-19.” medRxiv, March, 2020.03.03.20029983. https://doi.org/10.1101/2020.03.03.20029983.

Woelfel, Roman, Victor Max Corman, Wolfgang Guggemos, Michael Seilmaier, Sabine Zange, Marcel A. Mueller, Daniela Niemeyer, et al. 2020. “Clinical Presentation and Virological Assessment of Hospitalized Cases of Coronavirus Disease 2019 in a Travel-Associated Transmission Cluster.” medRxiv, March, 2020.03.05.20030502. https://doi.org/10.1101/2020.03.05.20030502.

Wu, Zunyou, and Jennifer M. McGoogan. 2020. “Characteristics of and Important Lessons from the Coronavirus Disease 2019 (COVID-19) Outbreak in China: Summary of a Report of 72 314 Cases from the Chinese Center for Disease Control and Prevention.” JAMA, February. https://doi.org/10.1001/jama.2020.2648.

Yang, Penghui, Yibo Ding, Zhe Xu, Rui Pu, Ping Li, Jin Yan, Jiluo Liu, et al. 2020. “Epidemiological and Clinical Features of COVID-19 Patients with and Without Pneumonia in Beijing, China.” medRxiv, March, 2020.02.28.20028068. https://doi.org/10.1101/2020.02.28.20028068.

Yang, Xiaobo, Yuan Yu, Jiqian Xu, Huaqing Shu, Jia’an Xia, Hong Liu, Yongran Wu, et al. 2020. “Clinical Course and Outcomes of Critically Ill Patients with SARS-CoV-2 Pneumonia in Wuhan, China: A Single-Centered, Retrospective, Observational Study.” The Lancet Respiratory Medicine 0 (0). https://doi.org/10.1016/S2213-2600(20)30079-5.

Zhao, Qingyuan, Yang Chen, and Dylan S. Small. 2020. “Analysis of the Epidemic Growth of the Early 2019-nCoV Outbreak Using Internationally Confirmed Cases.” medRxiv, February, 2020.02.06.20020941. https://doi.org/10.1101/2020.02.06.20020941.""")
        
    elif page == "Código":
        st.write("""Os códigos deste simulador estão no [GitHub](https://github.com/dumsantos/SEIR_COVID19_BR) e possuem uma versão em Python usando Streamlit e outra em R usando Shiny. Contate eduardo@cappra.com.br em caso de perguntas.

Agradecimento para Alison Hill que desenvolveu a ferramenta inicial em R, [Guilherme Machado](https://www.linkedin.com/in/guilhermermachado/) e [Caetano Slaviero](https://www.linkedin.com/in/caetanoslaviero/) que auxiliaram na tradução e codificação da versão em Python e também a todo o time da Cappra Institute for Data Science pelas pesquisas desenvolvidas.

Quer saber mais sobre o COVID-19, confira nosso [estudo](http://covid19.cappralab.com).""")
        


if __name__ == "__main__":
    main(IncubPeriod)
    

