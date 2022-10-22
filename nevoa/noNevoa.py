import random
from paho.mqtt import client as mqtt_client
import time
import pandas as pd


#parâmetros de conexão com o broker
broker = 'broker.emqx.io'
port = 1883
username = 'emqx'
password = 'public'
#gerando o ID
client_id = str(random.randint(0, 100))
dado = [] #bd da nuvem
nHidrometros = 0
hidrometrosConectados = []
setorNevoa = str(input('Digite aqui o setor do seu nó: \n'))

#recebe como parâmetro a matriz do nó
#retornaDataFrame com última ocorrência de cada ID
def ultimaoOcorrencia(db):
    listaHidrometros = []
    unicaOcorencia = []
    aux = 0
    for hidrometro in db: #para criar uma lista com a última ocorrência daquele hidrômetro
        id = hidrometro[3]    
        if id not in listaHidrometros: 
            listaHidrometros.append(id)
            unicaOcorencia.append(hidrometro)
            print(listaHidrometros)            
            aux = listaHidrometros.index(id)
        else:
            aux = listaHidrometros.index(id)
            unicaOcorencia.pop(aux)
            unicaOcorencia.append(hidrometro) 
            listaHidrometros.pop(aux)
            listaHidrometros.append(id)              
    tabelaDB =  pd.DataFrame(unicaOcorencia, columns= ['Litros Utilizados', 'Horário', 'Vazao atual', 'ID', 'Situacao']) #dataFrame com a última ocrrência de cada ID
    print('PRINT TABELA DB \n',tabelaDB)
    return tabelaDB

#retorna a média do nó/ utiliza o dataFrame para isso
def mediaNo(tabelaDB):
    media = tabelaDB['Litros Utilizados'].median()
    print('A média de litros utilizados é: ', media)
    return media

#bloqueia o hidrômetro por média geral do sistema
def bloqueioMediaGeral(tabelaDB, mediaGeral):
    print('bloqueio media geral')    
    bloqueioTabelaMediaGeral = tabelaDB.loc[tabelaDB['Litros Utilizados'] > mediaGeral] #filtramos com a média geral
    # bloqueioTabelaMediaGeral = tabelaDB.loc[tabelaDB['Litros Utilizados'] > mediaGeral, ['ID']] #aqui irá retornar o ID
    print(bloqueioTabelaMediaGeral)

#bloqueia hidrômetros por seu teto de gastos
def bloqueioTetoGasto(tabelaDB, tetoGasto, client):    
    topicoNevoa = 'bloqueio/'+ setorNevoa #será usado para enviar mensagens os hidrometros #bloqueio/desbloqueio    
    print('BLOQUEIO TETO DE GASTOS COM HIDRÔMETROS QUE GASTARAM MAIS QUE ', tetoGasto)
    bloqueioTabelaTestoGasto = tabelaDB.loc[tabelaDB['Litros Utilizados'] > tetoGasto, ['ID']] #aqui irá retornar o ID] #filtramos com o teto de gasto #o teto de gasto deve ser verificado ta todo momemento
    print(bloqueioTabelaTestoGasto)
    idTetoGastos = bloqueioTabelaTestoGasto['ID'].tolist() #retorna uma lista com apenas o ID do filtro já feito
    for id in idTetoGastos:
        mensagemBloqueio = 'bloquear/'+ str(id)  
        print(mensagemBloqueio)     
        result = client.publish(topicoNevoa, mensagemBloqueio) #bloquearHidro
    #depois é só pegar as id que foram retornadas

#Conecta-se ao broker
def connect_mqtt() -> mqtt_client:  
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Conectado ao broker com sucesso ")
        else:
            print("Erro na conexão %d\n", rc)

    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client 

'''Manipula mensagens recebidas pelo tópico dos hidrômetros'''
def recebeHidrometros(client, msg):
    listaAux = []
    idHidro = msg.topic
    print('Recebendo mensagem', msg.topic)
    aux, setorHidrometro ,  id = idHidro.split('/')   #pegando a id do hidrômetro
    if id not in hidrometrosConectados: #conferindo se já existe essa ID na lista
        hidrometrosConectados.append(id)                
        print('hidrometros conectados', nHidrometros , '\n')                  
    mensagem = msg.payload.decode()            
    listrosUtilizados, dataH, vazao, id, vaza, *temp = mensagem.split(',')    #a variável temp é aux para o demsempacotamento c o split
    listaAux.append(int(listrosUtilizados))
    listaAux.append(dataH)
    listaAux.append(int(vazao))
    listaAux.append(id)
    listaAux.append(vaza)        
    print('\nLitros utilizados: ' + listrosUtilizados)
    print('\nHorário/Data: ' + dataH)
    print('\nVazão atual: ' + vazao)
    print('\n ID:' + id)
    print('\n Situção de vazamento (0 para vazamento e 1 para não)'+ vaza , '\n')
    dado.append(listaAux)
    return dado 

#inscreve-se no tópico do servidor e trata as mensagens, de acordo com o tópico que está sendo recebido
def subscribeServer(client: mqtt_client): 
    global dado    
    global hidrometrosConectados
    global nHidrometros
    listaNevoa = [] 
    def on_message(client, userdata, msg):
        topico = msg.topic        
        aux, setorHidrometro,  id = topico.split('/')   #pegando qual é o tópico
        if aux == 'nevoa': #aqui vai ser usado para receber mensagens do server            
           print ('TÓPICO DA NEVOA')  
           mensagem = msg.payload.decode()           
           listaNevoa.append(mensagem)
           print('Nós: número de hidrômetros conectados')
        else: #tópico dos hidrometros
            print('TÓPICO DO HIDRÔMETROS')
            dado = recebeHidrometros(client, msg)        
    client.subscribe("nevoa/#")          
    client.on_message = on_message


#envia para servidor central a média do hidrômetro    
def publish(client):
    global dado   
    global setorNevoa  
    global tabelaDB  
    status = 0
    noNevoa = str(random.randint(1024,5000)) #gera id do nó
    topicoNo = 'NoNevoa/'+ noNevoa  #tópico que conecta com o servidor    
    while True:
        print('-'*10)
        print('-'*10)
        time.sleep(4)      #aqui é pra regular a quantidade de tempo que ele vai atualizar         
        if status == 0:
            print(f"Enviando para Servidor\n")            
            tabela = ultimaoOcorrencia(dado)
            tetoGasto = int(10)
            bloqueioTetoGasto(tabela, tetoGasto, client)
            time.sleep(2) #colocar um tempo maior
        else:
            print(f"Erro na rede. Mensagens não estão sendo enviadas para Servidor")  


def subscribeHidrometros(client: mqtt_client): 
    def on_message(client, userdata, msg):           
        topico = msg.topic  
        print('Recebendo mensagem', msg.topic)  
    client.subscribe('Hidrometros/'+setorNevoa+'/#') 
    client.on_message = on_message 

def run():
    client = connect_mqtt()
    client.loop_start()   # type: ignore
    subscribeHidrometros(client)
    subscribeServer(client)    
    publish(client) 

if __name__ == '__main__':
    run()