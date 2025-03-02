from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import random
import pandas as pd
import io
import os
from werkzeug.utils import secure_filename
import json

# Inicialização da aplicação
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave_secreta_yggdrasil'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///yggdrasil.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.jinja_env.globals.update(min=min)

# Criação da pasta de uploads se não existir
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Inicialização do banco de dados
db = SQLAlchemy(app)
migrate = Migrate(app, db)
with app.app_context():
    db.create_all()
    print("Banco de dados inicializado!")

# Modelos
class Disciplina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    questoes = db.relationship('Questao', backref='disciplina', lazy=True)
    topicos = db.relationship('Topico', backref='disciplina', lazy=True)
    
    def calcular_estatisticas(self):
        total_questoes = len(self.questoes)
        if total_questoes == 0:
            return {
                'acertos_percentual': 0,
                'erros_por_questao': 0,
                'total_questoes': 0,
                'questoes_acertadas': 0,
                'total_erros': 0,
                'questoes_erradas': 0,
                'erros_percentual': 0
            }
        
        questoes_acertadas = sum(1 for q in self.questoes if q.numero_acertos > 0)
        questoes_erradas = sum(1 for q in self.questoes if q.numero_erros > 0)
        total_erros = sum(q.numero_erros for q in self.questoes)
        
        return {
            'acertos_percentual': round((questoes_acertadas / total_questoes) * 100, 2),
            'erros_percentual': round((questoes_erradas / total_questoes) * 100, 2),
            'erros_por_questao': round(total_erros / total_questoes, 2) if total_questoes > 0 else 0,
            'total_questoes': total_questoes,
            'questoes_acertadas': questoes_acertadas,
            'questoes_erradas': questoes_erradas,
            'total_erros': total_erros
        }

class Topico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplina.id'), nullable=False)
    questoes = db.relationship('Questao', backref='topico', lazy=True)
    
    def calcular_estatisticas(self):
        total_questoes = len(self.questoes)
        if total_questoes == 0:
            return {
                'acertos_percentual': 0,
                'erros_por_questao': 0,
                'total_questoes': 0,
                'questoes_acertadas': 0,
                'total_erros': 0
            }
        
        questoes_acertadas = sum(1 for q in self.questoes if q.numero_acertos > 0)
        total_erros = sum(q.numero_erros for q in self.questoes)
        
        return {
            'acertos_percentual': round((questoes_acertadas / total_questoes) * 100, 2),
            'erros_por_questao': round(total_erros / total_questoes, 2) if total_questoes > 0 else 0,
            'total_questoes': total_questoes,
            'questoes_acertadas': questoes_acertadas,
            'total_erros': total_erros
        }

class Questao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enunciado = db.Column(db.Text, nullable=False)
    gabarito = db.Column(db.Boolean, nullable=False)  # True para CERTO, False para ERRADO
    justificativa = db.Column(db.Text, nullable=False)
    disciplina_id = db.Column(db.Integer, db.ForeignKey('disciplina.id'), nullable=False)
    topico_id = db.Column(db.Integer, db.ForeignKey('topico.id'), nullable=False)
    numero_acertos = db.Column(db.Integer, default=0)
    numero_erros = db.Column(db.Integer, default=0)
    ultima_data = db.Column(db.Date, default=datetime.now().date)
    proxima_data = db.Column(db.Date, default=datetime.now().date)
    status = db.Column(db.Boolean, default=True)  # True para ativada, False para desativada

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Dias para adiar após acerto com diferentes níveis de confiança
    dias_acerto_certeza_min = db.Column(db.Integer, default=12)
    dias_acerto_certeza_max = db.Column(db.Integer, default=15)
    
    dias_acerto_confiante_min = db.Column(db.Integer, default=5)
    dias_acerto_confiante_max = db.Column(db.Integer, default=8)
    
    dias_acerto_duvida_min = db.Column(db.Integer, default=2)
    dias_acerto_duvida_max = db.Column(db.Integer, default=4)
    
    # Dias para adiar após erro com diferentes níveis de confiança
    dias_erro_certeza = db.Column(db.Integer, default=1)
    dias_erro_confiante = db.Column(db.Integer, default=1)
    dias_erro_duvida = db.Column(db.Integer, default=1)
    
    # Configuração para mostrar quantas questões por página
    questoes_por_pagina = db.Column(db.Integer, default=20)

    @staticmethod
    def get_config():
        """Obtém a configuração atual ou cria uma configuração padrão se não existir"""
        config = Configuracao.query.first()
        if not config:
            config = Configuracao()
            db.session.add(config)
            db.session.commit()
        return config

# Rotas
@app.route('/')
def index():
    disciplinas = Disciplina.query.all()
    for disciplina in disciplinas:
        disciplina.estatisticas = disciplina.calcular_estatisticas()
    
    return render_template('index.html', disciplinas=disciplinas)

@app.route('/disciplina/<int:disciplina_id>')
def ver_disciplina(disciplina_id):
    disciplina = Disciplina.query.get_or_404(disciplina_id)
    topicos = Topico.query.filter_by(disciplina_id=disciplina_id).all()
    
    for topico in topicos:
        topico.estatisticas = topico.calcular_estatisticas()
    
    disciplina.estatisticas = disciplina.calcular_estatisticas()
    
    return render_template('disciplina.html', disciplina=disciplina, topicos=topicos)

@app.route('/topico/<int:topico_id>')
def ver_topico(topico_id):
    topico = Topico.query.get_or_404(topico_id)
    topico.estatisticas = topico.calcular_estatisticas()
    
    return render_template('topico.html', topico=topico)

@app.route('/revisao')
def revisao():
    hoje = datetime.now().date()
    
    # Questões programadas para hoje ou antes, que estejam ativas
    questoes = Questao.query.filter(
        Questao.proxima_data <= hoje,
        Questao.status == True
    ).all()
    
    if not questoes:
        flash('Não há questões para revisar hoje!', 'info')
        return redirect(url_for('index'))
    
    # Agrupar questões por data para desempate com aleatoriedade
    questoes_por_data = {}
    
    for questao in questoes:
        data_chave = questao.proxima_data.strftime('%Y-%m-%d')
        if data_chave not in questoes_por_data:
            questoes_por_data[data_chave] = []
        questoes_por_data[data_chave].append(questao)
    
    # Reorganizar com aleatoriedade para datas iguais
    questoes_ordenadas = []
    
    # Ordenar as datas (as mais antigas primeiro)
    for data in sorted(questoes_por_data.keys()):
        # Embaralhar questões com a mesma data
        random.shuffle(questoes_por_data[data])
        # Ordenar por número de erros (desempate secundário)
        questoes_por_data[data].sort(key=lambda q: q.numero_erros, reverse=True)
        questoes_ordenadas.extend(questoes_por_data[data])
    
    # Agrupar questões por disciplina para melhor distribuição
    questoes_por_disciplina = {}
    
    for questao in questoes_ordenadas:
        disciplina_id = questao.disciplina_id
        if disciplina_id not in questoes_por_disciplina:
            questoes_por_disciplina[disciplina_id] = []
        questoes_por_disciplina[disciplina_id].append(questao)
    
    # Reorganizar para intercalar disciplinas
    questoes_reorganizadas = []
    ainda_tem_questoes = True
    
    while ainda_tem_questoes:
        ainda_tem_questoes = False
        for disciplina_id in list(questoes_por_disciplina.keys()):
            if questoes_por_disciplina[disciplina_id]:
                questoes_reorganizadas.append(questoes_por_disciplina[disciplina_id].pop(0))
                ainda_tem_questoes = True
    
    # Guardar IDs das questões na sessão para controle
    session['questoes_revisao'] = [q.id for q in questoes_reorganizadas]
    session['indice_atual'] = 0
    session['modo_estudo'] = 'revisao'
    
    return redirect(url_for('mostrar_questao', modo='revisao'))

@app.route('/escolher_ordem/<string:modo>/<int:id_ref>')
def escolher_ordem(modo, id_ref):
    # Verificar se existem questões para a disciplina/tópico
    if modo == 'disciplina':
        questoes = Questao.query.filter_by(disciplina_id=id_ref, status=True).all()
        nome_referencia = Disciplina.query.get_or_404(id_ref).nome
    elif modo == 'topico':
        questoes = Questao.query.filter_by(topico_id=id_ref, status=True).all()
        nome_referencia = Topico.query.get_or_404(id_ref).nome
    else:
        flash('Modo inválido!', 'error')
        return redirect(url_for('index'))
    
    if not questoes:
        flash('Não há questões disponíveis nesta categoria!', 'info')
        if modo == 'disciplina':
            return redirect(url_for('ver_disciplina', disciplina_id=id_ref))
        else:
            return redirect(url_for('ver_topico', topico_id=id_ref))
    
    return render_template('modal_ordem.html', modo=modo, id_ref=id_ref, nome_referencia=nome_referencia)


# Modificar a função 'aleatorio' para aceitar o parâmetro de ordem
@app.route('/aleatorio/<string:modo>/<int:id_ref>')
@app.route('/aleatorio/<string:modo>/<int:id_ref>/<string:ordem>')
def aleatorio(modo, id_ref, ordem='aleatoria'):
    if modo == 'disciplina':
        questoes = Questao.query.filter_by(disciplina_id=id_ref, status=True).all()
    elif modo == 'topico':
        questoes = Questao.query.filter_by(topico_id=id_ref, status=True).all()
    else:
        flash('Modo inválido!', 'error')
        return redirect(url_for('index'))
    
    if not questoes:
        flash('Não há questões disponíveis nesta categoria!', 'info')
        if modo == 'disciplina':
            return redirect(url_for('ver_disciplina', disciplina_id=id_ref))
        else:
            return redirect(url_for('ver_topico', topico_id=id_ref))
    
    # Ordenar questões conforme solicitado
    if ordem == 'proxima_data':
        questoes.sort(key=lambda q: q.proxima_data)
    else:  # aleatória
        random.shuffle(questoes)
    
    # Guardar IDs das questões na sessão
    session['questoes_revisao'] = [q.id for q in questoes]
    session['indice_atual'] = 0
    session['modo_estudo'] = modo
    session['id_referencia'] = id_ref
    
    return redirect(url_for('mostrar_questao', modo=f'{modo}_{id_ref}'))


# Adicionar rota para a modalidade "Difíceis"
@app.route('/dificeis')
def questoes_dificeis():
    # Filtrar questões com mais erros que acertos
    questoes = Questao.query.filter(
        Questao.status == True,
        Questao.numero_erros > Questao.numero_acertos
    ).order_by(Questao.numero_erros.desc()).all()
    
    if not questoes:
        flash('Não há questões difíceis disponíveis!', 'info')
        return redirect(url_for('index'))
    
    # Guardar IDs das questões na sessão
    session['questoes_revisao'] = [q.id for q in questoes]
    session['indice_atual'] = 0
    
    return redirect(url_for('mostrar_questao', modo='dificeis'))

@app.route('/distantes')
def questoes_distantes():
    # Ordenar questões ativas por data de última aparição (mais antigas primeiro)
    questoes = Questao.query.filter_by(status=True).order_by(Questao.ultima_data.asc()).limit(50).all()
    
    if not questoes:
        flash('Não há questões disponíveis!', 'info')
        return redirect(url_for('index'))
    
    # Guardar IDs das questões na sessão
    session['questoes_revisao'] = [q.id for q in questoes]
    session['indice_atual'] = 0
    
    return redirect(url_for('mostrar_questao', modo='distantes'))

@app.route('/questao/<string:modo>')
def mostrar_questao(modo):
    if 'questoes_revisao' not in session or 'indice_atual' not in session:
        flash('Sessão de estudo inválida!', 'error')
        return redirect(url_for('index'))
    
    indice = session['indice_atual']
    ids_questoes = session['questoes_revisao']
    
    if indice >= len(ids_questoes):
        # Verificar se era um simulado para mostrar o relatório
        if session.get('modo_estudo') == 'simulado' and 'simulado_stats' in session:
            print("Redirecionando para o relatório do simulado")  # Para debug
            return redirect(url_for('relatorio_simulado'))
        
        flash('Você concluiu todas as questões desta sessão!', 'success')
        return redirect(url_for('index'))
    
    questao = Questao.query.get_or_404(ids_questoes[indice])
    progresso = f"{indice + 1}/{len(ids_questoes)}"
    
    return render_template('questao.html', questao=questao, modo=modo, progresso=progresso)

@app.route('/responder', methods=['POST'])
def responder():
    questao_id = request.form.get('questao_id')
    resposta = request.form.get('resposta') == 'true'  # Converte string para boolean
    confianca = request.form.get('confianca', 'confiante')  # Valor padrão é 'confiante'
    
    questao = Questao.query.get_or_404(questao_id)
    acertou = resposta == questao.gabarito
    
    # Obter configurações
    config = Configuracao.get_config()
    
    # Atualizar estatísticas
    if acertou:
        questao.numero_acertos += 1
        
        # Definir próxima data com base no nível de confiança e no histórico
        # Com validação para valores nulos
        if confianca == 'certeza':
            dias_min = config.dias_acerto_certeza_min or 12  # Valor padrão se for None
            dias_max = config.dias_acerto_certeza_max or 15  # Valor padrão se for None
        elif confianca == 'confiante':
            dias_min = config.dias_acerto_confiante_min or 5  # Valor padrão se for None
            dias_max = config.dias_acerto_confiante_max or 8  # Valor padrão se for None
        else:  # dúvida
            dias_min = config.dias_acerto_duvida_min or 2  # Valor padrão se for None
            dias_max = config.dias_acerto_duvida_max or 4  # Valor padrão se for None
        
        # Ajustar baseado no histórico da questão
        diferenca_acertos_erros = questao.numero_acertos - questao.numero_erros
        if diferenca_acertos_erros > 0:
            # Adiciona até 3 dias extras para cada 2 acertos a mais que erros
            bonus_dias = min(6, diferenca_acertos_erros // 2)
            dias_max += bonus_dias
            dias_min += bonus_dias // 2
        
        # Escolher um valor aleatório dentro do range
        dias_espera = random.randint(int(dias_min), int(dias_max))
        questao.proxima_data = datetime.now().date() + timedelta(days=dias_espera)
    else:
        questao.numero_erros += 1
        
        # Definir próxima data com base no nível de confiança
        if confianca == 'certeza':
            dias_espera = config.dias_erro_certeza or 1  # Valor padrão se for None
        elif confianca == 'confiante':
            dias_espera = config.dias_erro_confiante or 1  # Valor padrão se for None
        else:  # dúvida
            dias_espera = config.dias_erro_duvida or 1  # Valor padrão se for None
        
        # Reduzir o tempo de espera se houve mais erros que acertos
        if questao.numero_erros > questao.numero_acertos:
            dias_espera = max(1, dias_espera - (questao.numero_erros - questao.numero_acertos) // 2)
            
        questao.proxima_data = datetime.now().date() + timedelta(days=dias_espera)
    
    # Atualizar data da última aparição
    questao.ultima_data = datetime.now().date()
    
    # Armazenar estatísticas para o relatório de simulado, se necessário
    modo = session.get('modo_estudo', '')
    if modo == 'simulado':
        # Inicializar estatísticas do simulado se ainda não existirem
        if 'simulado_stats' not in session:
            session['simulado_stats'] = {
                'questoes': [],
                'respostas': {},
                'disciplinas': {},
                'confianca': {
                    'acertos': {'certeza': 0, 'confiante': 0, 'duvida': 0},
                    'erros': {'certeza': 0, 'confiante': 0, 'duvida': 0},
                    'total': {'certeza': 0, 'confiante': 0, 'duvida': 0}
                }
            }
        
        # Registrar resposta
        session['simulado_stats']['respostas'][questao_id] = {
            'acertou': acertou,
            'confianca': confianca,
            'disciplina_id': questao.disciplina_id,
            'disciplina_nome': questao.disciplina.nome
        }
        
        # Atualizar contadores por disciplina
        disc_id = str(questao.disciplina_id)
        if disc_id not in session['simulado_stats']['disciplinas']:
            session['simulado_stats']['disciplinas'][disc_id] = {
                'nome': questao.disciplina.nome,
                'acertos': 0,
                'total': 0
            }
        
        session['simulado_stats']['disciplinas'][disc_id]['total'] += 1
        if acertou:
            session['simulado_stats']['disciplinas'][disc_id]['acertos'] += 1
        
        # Atualizar contadores por nível de confiança
        session['simulado_stats']['confianca']['total'][confianca] += 1
        if acertou:
            session['simulado_stats']['confianca']['acertos'][confianca] += 1
        else:
            session['simulado_stats']['confianca']['erros'][confianca] += 1
        
        # Salvar sessão atualizada
        session.modified = True
    
    db.session.commit()
    
    # Avançar para a próxima questão
    session['indice_atual'] = session.get('indice_atual', 0) + 1
    
    return jsonify({
        'acertou': acertou,
        'justificativa': questao.justificativa,
        'proxima_questao': session.get('indice_atual', 0) < len(session.get('questoes_revisao', []))
    })

@app.route('/denunciar', methods=['POST'])
def denunciar():
    questao_id = request.form.get('questao_id')
    
    questao = Questao.query.get_or_404(questao_id)
    questao.status = False
    
    db.session.commit()
    
    # Avançar para a próxima questão
    session['indice_atual'] = session.get('indice_atual', 0) + 1
    
    return jsonify({
        'success': True,
        'proxima_questao': session.get('indice_atual', 0) < len(session.get('questoes_revisao', []))
    })

@app.route('/simulado', methods=['GET', 'POST'])
def simulado():
    if request.method == 'GET':
        disciplinas = Disciplina.query.all()
        return render_template('simulado.html', disciplinas=disciplinas)
    
    # Processar configuração do simulado
    questoes_por_disciplina = {}
    questoes_selecionadas = []
    
    for key, value in request.form.items():
        if key.startswith('disciplina_') and value and int(value) > 0:
            disciplina_id = int(key.split('_')[1])
            questoes_por_disciplina[disciplina_id] = int(value)
    
    # Selecionar questões aleatórias de cada disciplina
    for disciplina_id, quantidade in questoes_por_disciplina.items():
        questoes = Questao.query.filter_by(disciplina_id=disciplina_id, status=True).all()
        if questoes:
            selecionadas = random.sample(questoes, min(quantidade, len(questoes)))
            questoes_selecionadas.extend([q.id for q in selecionadas])
    
    if not questoes_selecionadas:
        flash('Nenhuma questão selecionada para o simulado!', 'error')
        return redirect(url_for('simulado'))
    
    # Embaralhar questões
    random.shuffle(questoes_selecionadas)
    
    # Inicializar estatísticas do simulado
    session['simulado_stats'] = {
        'questoes': questoes_selecionadas,
        'respostas': {},
        'disciplinas': {},
        'confianca': {
            'acertos': {'certeza': 0, 'confiante': 0, 'duvida': 0},
            'erros': {'certeza': 0, 'confiante': 0, 'duvida': 0},
            'total': {'certeza': 0, 'confiante': 0, 'duvida': 0}
        }
    }
    
    # Guardar na sessão
    session['questoes_revisao'] = questoes_selecionadas
    session['indice_atual'] = 0
    session['modo_estudo'] = 'simulado'  # Importante para o rastreamento correto
    
    return redirect(url_for('mostrar_questao', modo='simulado'))

@app.route('/gerenciar')
def gerenciar():
    return render_template('gerenciar.html')

@app.route('/adicionar_questao', methods=['GET', 'POST'])
def adicionar_questao():
    if request.method == 'GET':
        disciplinas = Disciplina.query.all()
        return render_template('adicionar_questao.html', disciplinas=disciplinas)
    
    # Processar adição de questão
    enunciado = request.form.get('enunciado')
    gabarito = request.form.get('gabarito') == 'true'
    justificativa = request.form.get('justificativa')
    disciplina_id = request.form.get('disciplina_id')
    topico_id = request.form.get('topico_id')
    
    nova_questao = Questao(
        enunciado=enunciado,
        gabarito=gabarito,
        justificativa=justificativa,
        disciplina_id=disciplina_id,
        topico_id=topico_id,
        ultima_data=datetime.now().date(),
        proxima_data=datetime.now().date()
    )
    
    db.session.add(nova_questao)
    db.session.commit()
    
    flash('Questão adicionada com sucesso!', 'success')
    return redirect(url_for('adicionar_questao'))

@app.route('/importar', methods=['GET', 'POST'])
def importar():
    if request.method == 'GET':
        disciplinas = Disciplina.query.all()
        return render_template('importar.html', disciplinas=disciplinas)
    
    # Processar upload de arquivo
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado!', 'error')
        return redirect(url_for('importar'))
    
    arquivo = request.files['arquivo']
    disciplina_id = request.form.get('disciplina_id')
    topico_id = request.form.get('topico_id')
    
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado!', 'error')
        return redirect(url_for('importar'))
    
    if not disciplina_id or not topico_id:
        flash('Selecione a disciplina e o tópico!', 'error')
        return redirect(url_for('importar'))
    
    # Verificar extensão
    extensao = arquivo.filename.rsplit('.', 1)[1].lower()
    if extensao not in ['csv', 'xlsx']:
        flash('Formato de arquivo não suportado!', 'error')
        return redirect(url_for('importar'))
    
    # Processar arquivo
    try:
        if extensao == 'csv':
            df = pd.read_csv(io.BytesIO(arquivo.read()), encoding='utf-8')
        else:  # xlsx
            df = pd.read_excel(io.BytesIO(arquivo.read()))
        
        # Verificar colunas necessárias
        colunas_necessarias = ['enunciado', 'gabarito', 'justificativa']
        if not all(coluna in df.columns for coluna in colunas_necessarias):
            flash('O arquivo não contém as colunas necessárias!', 'error')
            return redirect(url_for('importar'))
        
        # Adicionar questões
        contador = 0
        for _, row in df.iterrows():
            # Converter gabarito para boolean (True para CERTO, False para ERRADO)
            gabarito_valor = row['gabarito']
            if isinstance(gabarito_valor, str):
                gabarito = gabarito_valor.upper() in ['CERTO', 'TRUE', 'V', 'VERDADEIRO', 'SIM', 'S', 'C', '1']
            else:
                gabarito = bool(gabarito_valor)
            
            nova_questao = Questao(
                enunciado=row['enunciado'],
                gabarito=gabarito,
                justificativa=row['justificativa'],
                disciplina_id=disciplina_id,
                topico_id=topico_id,
                ultima_data=datetime.now().date(),
                proxima_data=datetime.now().date()
            )
            
            db.session.add(nova_questao)
            contador += 1
        
        db.session.commit()
        flash(f'{contador} questões importadas com sucesso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao processar arquivo: {str(e)}', 'error')
    
    return redirect(url_for('importar'))

@app.route('/listar_questoes')
def listar_questoes():
    disciplina_id = request.args.get('disciplina_id')
    topico_id = request.args.get('topico_id')
    status = request.args.get('status')
    
    query = Questao.query
    
    if disciplina_id:
        query = query.filter_by(disciplina_id=disciplina_id)
    
    if topico_id:
        query = query.filter_by(topico_id=topico_id)
    
    if status:
        if status == 'ativas':
            query = query.filter_by(status=True)
        elif status == 'desativadas':
            query = query.filter_by(status=False)
    
    # Obter configuração para paginação
    config = Configuracao.get_config()
    
    # Adicionar ordenação
    query = query.order_by(Questao.disciplina_id, Questao.topico_id, Questao.id)
    
    questoes = query.all()
    disciplinas = Disciplina.query.all()
    
    return render_template('listar_questoes.html', questoes=questoes, disciplinas=disciplinas)

@app.route('/editar_questao/<int:questao_id>', methods=['GET', 'POST'])
def editar_questao(questao_id):
    questao = Questao.query.get_or_404(questao_id)
    
    if request.method == 'GET':
        disciplinas = Disciplina.query.all()
        topicos = Topico.query.filter_by(disciplina_id=questao.disciplina_id).all()
        return render_template('editar_questao.html', questao=questao, disciplinas=disciplinas, topicos=topicos)
    
    # Processar edição
    questao.enunciado = request.form.get('enunciado')
    questao.gabarito = request.form.get('gabarito') == 'true'
    questao.justificativa = request.form.get('justificativa')
    questao.disciplina_id = request.form.get('disciplina_id')
    questao.topico_id = request.form.get('topico_id')
    questao.status = request.form.get('status') == 'true'
    
    db.session.commit()
    flash('Questão atualizada com sucesso!', 'success')
    
    return redirect(url_for('listar_questoes'))

@app.route('/adicionar_disciplina', methods=['GET', 'POST'])
def adicionar_disciplina():
    if request.method == 'GET':
        return render_template('adicionar_disciplina.html')
    
    nome = request.form.get('nome')
    
    if not nome:
        flash('Nome da disciplina é obrigatório!', 'error')
        return redirect(url_for('adicionar_disciplina'))
    
    # Verificar se já existe
    if Disciplina.query.filter_by(nome=nome).first():
        flash('Esta disciplina já existe!', 'error')
        return redirect(url_for('adicionar_disciplina'))
    
    nova_disciplina = Disciplina(nome=nome)
    db.session.add(nova_disciplina)
    db.session.commit()
    
    flash('Disciplina adicionada com sucesso!', 'success')
    return redirect(url_for('gerenciar'))

@app.route('/adicionar_topico', methods=['GET', 'POST'])
def adicionar_topico():
    if request.method == 'GET':
        disciplinas = Disciplina.query.all()
        return render_template('adicionar_topico.html', disciplinas=disciplinas)
    
    nome = request.form.get('nome')
    disciplina_id = request.form.get('disciplina_id')
    
    if not nome or not disciplina_id:
        flash('Nome do tópico e disciplina são obrigatórios!', 'error')
        return redirect(url_for('adicionar_topico'))
    
    novo_topico = Topico(nome=nome, disciplina_id=disciplina_id)
    db.session.add(novo_topico)
    db.session.commit()
    
    flash('Tópico adicionado com sucesso!', 'success')
    return redirect(url_for('gerenciar'))

@app.route('/get_topicos/<int:disciplina_id>')
def get_topicos(disciplina_id):
    topicos = Topico.query.filter_by(disciplina_id=disciplina_id).all()
    return jsonify([{'id': t.id, 'nome': t.nome} for t in topicos])


@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    config = Configuracao.get_config()
    
    # Garantir que todas as propriedades tenham valores válidos
    if config.dias_acerto_certeza_min is None:
        config.dias_acerto_certeza_min = 12
    if config.dias_acerto_certeza_max is None:
        config.dias_acerto_certeza_max = 15
    if config.dias_acerto_confiante_min is None:
        config.dias_acerto_confiante_min = 5
    if config.dias_acerto_confiante_max is None:
        config.dias_acerto_confiante_max = 8
    if config.dias_acerto_duvida_min is None:
        config.dias_acerto_duvida_min = 2
    if config.dias_acerto_duvida_max is None:
        config.dias_acerto_duvida_max = 4
    if config.dias_erro_certeza is None:
        config.dias_erro_certeza = 1
    if config.dias_erro_confiante is None:
        config.dias_erro_confiante = 1
    if config.dias_erro_duvida is None:
        config.dias_erro_duvida = 1
    if config.questoes_por_pagina is None:
        config.questoes_por_pagina = 20
    
    # Salvar valores padrão se algum campo estiver nulo
    db.session.commit()
    
    if request.method == 'POST':
        # Atualizar configurações
        config.dias_acerto_certeza_min = int(request.form.get('dias_acerto_certeza_min', 12))
        config.dias_acerto_certeza_max = int(request.form.get('dias_acerto_certeza_max', 15))
        
        config.dias_acerto_confiante_min = int(request.form.get('dias_acerto_confiante_min', 5))
        config.dias_acerto_confiante_max = int(request.form.get('dias_acerto_confiante_max', 8))
        
        config.dias_acerto_duvida_min = int(request.form.get('dias_acerto_duvida_min', 2))
        config.dias_acerto_duvida_max = int(request.form.get('dias_acerto_duvida_max', 4))
        
        config.dias_erro_certeza = int(request.form.get('dias_erro_certeza', 1))
        config.dias_erro_confiante = int(request.form.get('dias_erro_confiante', 1))
        config.dias_erro_duvida = int(request.form.get('dias_erro_duvida', 1))
        
        config.questoes_por_pagina = int(request.form.get('questoes_por_pagina', 20))
        
        db.session.commit()
        
        flash('Configurações atualizadas com sucesso!', 'success')
        return redirect(url_for('configuracoes'))
    
    return render_template('configuracoes.html', config=config)

@app.route('/alternar_status_questao', methods=['POST'])
def alternar_status_questao():
    questao_id = request.form.get('questao_id')
    novo_status = request.form.get('status') == 'true'
    
    questao = Questao.query.get_or_404(questao_id)
    questao.status = novo_status
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/relatorio_simulado')
def relatorio_simulado():
    if 'simulado_stats' not in session:
        flash('Nenhum simulado realizado recentemente!', 'error')
        return redirect(url_for('simulado'))
    
    # Calcular estatísticas totais
    stats = session['simulado_stats']
    respostas = stats.get('respostas', {})
    
    total_questoes = len(respostas)
    if total_questoes == 0:
        flash('Não há dados de simulado para gerar o relatório!', 'error')
        return redirect(url_for('simulado'))
        
    total_acertos = sum(1 for r in respostas.values() if r.get('acertou', False))
    total_erros = total_questoes - total_acertos
    
    # Certificar-se de que temos disciplinas e estatísticas de confiança
    if 'disciplinas' not in stats or 'confianca' not in stats:
        flash('Dados de simulado incompletos!', 'error')
        return redirect(url_for('simulado'))
    
    # Limpar as estatísticas da sessão depois de mostrar o relatório
    simulado_stats = session.pop('simulado_stats', None)
    
    # Imprimir para debug
    print(f"Relatório gerado: {total_questoes} questões, {total_acertos} acertos, {simulado_stats['disciplinas']}")
    
    return render_template('relatorio_simulado.html',
                           total_questoes=total_questoes,
                           total_acertos=total_acertos,
                           total_erros=total_erros,
                           disciplinas_stats=simulado_stats['disciplinas'],
                           confianca_stats=simulado_stats['confianca'])

# Inicialização do banco de dados
def init_db():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    init_db()  # Inicializa o banco de dados
    app.run(debug=True)
