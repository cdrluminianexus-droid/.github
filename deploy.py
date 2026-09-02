#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lumia Nexus Deployment Tool (Ferramenta de Implantação Lumia Nexus)
-----------------------------------------------------------------
Este programa centraliza a automação de CI/CD para os projetos da Lumia Nexus.
Substitui ou complementa os workflows reutilizáveis do GitHub Actions, permitindo a execução
totalmente em Python de forma robusta e modular.

Suporta:
1. Website: Compilação e implantação no GitHub Pages, Vercel ou Netlify.
2. Android: Compilação com Gradle, decodificação de Keystore, assinatura de App Bundle (.aab) e publicação na Google Play.
3. iOS: Configuração de chaveiro (keychain), importação de certificados, build do Xcode, exportação de IPA e upload ao TestFlight.
"""

import os
import sys
import argparse
import base64
import shutil
import tempfile
import json
import logging
import plistlib
import glob
import secrets
import subprocess
from typing import List, Optional, Dict, Any

# Configuração de Logs em Português e Inglês para máxima clareza
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LumiaDeploy")

def mask_sensitive_data(cmd: List[str]) -> str:
    """Oculta informações sensíveis (como senhas e tokens) de um comando antes de logar."""
    masked_parts = []
    skip_next = False
    
    sensitive_flags = {
        "-storepass", "-keypass", "-P", "-p", "--apiKey", "--apiIssuer", "--token",
        "--ks-pass", "--key-pass"
    }
    
    for part in cmd:
        if skip_next:
            masked_parts.append("********")
            skip_next = False
            continue
            
        if part in sensitive_flags:
            masked_parts.append(part)
            skip_next = True
        elif any(sec in part.lower() for sec in ["pass:", "token=", "key="]):
            masked_parts.append("********")
        else:
            masked_parts.append(part)
            
    return " ".join(masked_parts)

def run_command(cmd: List[str], shell: bool = False, env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """Executa um comando de sistema de forma segura e loga a saída."""
    masked_cmd_str = mask_sensitive_data(cmd) if isinstance(cmd, list) else cmd
    logger.info(f"Executando comando: {masked_cmd_str}")
    
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
            
        result = subprocess.run(
            cmd,
            shell=shell,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
            cwd=cwd
        )
        if result.stdout:
            logger.debug(f"Saída do comando:\n{result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao executar o comando: {masked_cmd_str}")
        logger.error(f"Código de saída: {e.returncode}")
        logger.error(f"Erro detalhado:\n{e.stderr}\n{e.stdout}")
        sys.exit(e.returncode)

def decode_base64_to_file(b64_str: str, dest_path: str) -> None:
    """Decodifica uma string base64 e salva em um arquivo de destino."""
    logger.info(f"Decodificando conteúdo Base64 para: {dest_path}")
    try:
        # Remover espaços em branco ou quebras de linha que possam corromper o base64
        cleaned_b64 = "".join(b64_str.split())
        decoded_bytes = base64.b64decode(cleaned_b64)
        
        # Garante que o diretório pai existe
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        
        with open(dest_path, "wb") as f:
            f.write(decoded_bytes)
        logger.info("Decodificação realizada com sucesso!")
    except Exception as e:
        logger.error(f"Falha ao decodificar Base64 para {dest_path}: {e}")
        sys.exit(1)


class WebsiteDeployer:
    """Responsável por construir e implantar websites (Player One Website)."""
    
    def __init__(self, environment: str, node_version: str, build_command: str, dist_directory: str, provider: str):
        self.environment = environment
        self.node_version = node_version
        self.build_command = build_command
        self.dist_directory = dist_directory
        self.provider = provider

    def build(self) -> None:
        """Instala dependências e compila o site."""
        logger.info("Iniciando compilação do Website...")
        
        # Instalar dependências dependendo da presença de package-lock.json
        if os.path.exists("package-lock.json"):
            logger.info("Instalando dependências usando 'npm ci'...")
            run_command(["npm", "ci"])
        else:
            logger.info("Instalando dependências usando 'npm install'...")
            run_command(["npm", "install"])
            
        # Executar o comando de build
        logger.info(f"Executando comando de build: {self.build_command}")
        # Divide o build_command para executar como lista se não for shell puro
        run_command(self.build_command.split())

    def deploy(self, token: Optional[str] = None, vercel_org_id: Optional[str] = None, 
               vercel_project_id: Optional[str] = None, netlify_site_id: Optional[str] = None) -> None:
        """Implantar no provedor selecionado."""
        if self.provider == "github-pages":
            self._deploy_to_github_pages(token)
        elif self.provider == "vercel":
            self._deploy_to_vercel(token, vercel_org_id, vercel_project_id)
        elif self.provider == "netlify":
            self._deploy_to_netlify(token, netlify_site_id)
        else:
            logger.error(f"Provedor de deploy desconhecido: {self.provider}")
            sys.exit(1)

    def _deploy_to_github_pages(self, token: Optional[str]) -> None:
        """Implantar no GitHub Pages usando Git."""
        logger.info("Iniciando deploy para o GitHub Pages...")
        dist_path = os.path.abspath(self.dist_directory)
        
        if not os.path.exists(dist_path):
            logger.error(f"Diretório de distribuição '{dist_path}' não encontrado. Execute o build primeiro.")
            sys.exit(1)
            
        # Criar diretório temporário para isolar o deploy
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree(dist_path, temp_dir, dirs_exist_ok=True)
            
            # Inicializar repositório Git temporário
            run_command(["git", "init"], env={"GIT_DIR": None}, cwd=temp_dir)
            run_command(["git", "config", "user.name", "Lumia Deployerer"], env={"GIT_DIR": None}, cwd=temp_dir)
            run_command(["git", "config", "user.email", "deployer@lumianexus.com"], env={"GIT_DIR": None}, cwd=temp_dir)
            
            # Adicionar todos os arquivos e fazer commit
            run_command(["git", "add", "."], env={"GIT_DIR": None}, cwd=temp_dir)
            run_command(["git", "commit", "-m", "Deploy automatizado via Lumia Python Tool"], env={"GIT_DIR": None}, cwd=temp_dir)
            
            # Construir URL do repositório de destino com Token de autenticação se disponível
            repo_url = os.environ.get("GITHUB_REPOSITORY", "cdrluminianexus-droid/player-one-site")
            if token:
                remote_url = f"https://x-access-token:{token}@github.com/{repo_url}.git"
            else:
                remote_url = f"https://github.com/{repo_url}.git"
                
            # Adicionar remoto e forçar push para gh-pages
            run_command(["git", "remote", "add", "origin", remote_url], env={"GIT_DIR": None}, cwd=temp_dir)
            logger.info("Enviando alterações para o branch 'gh-pages'...")
            run_command(["git", "push", "--force", "origin", "HEAD:gh-pages"], env={"GIT_DIR": None}, cwd=temp_dir)
            
        logger.info("Deploy para o GitHub Pages concluído com sucesso!")

    def _deploy_to_vercel(self, token: Optional[str], org_id: Optional[str], project_id: Optional[str]) -> None:
        """Implantar no Vercel usando CLI."""
        logger.info("Iniciando deploy para o Vercel...")
        if not token:
            logger.error("VERCEL_DEPLOY_TOKEN não fornecido. Não é possível continuar o deploy para Vercel.")
            sys.exit(1)
            
        # Instalar Vercel CLI globalmente se não estiver instalado
        if not shutil.which("vercel"):
            logger.info("Vercel CLI não encontrado. Instalando via npm...")
            run_command(["npm", "install", "-g", "vercel"])
            
        env = {
            "VERCEL_ORG_ID": org_id or os.environ.get("VERCEL_ORG_ID", ""),
            "VERCEL_PROJECT_ID": project_id or os.environ.get("VERCEL_PROJECT_ID", "")
        }
        
        cmd = ["vercel", "deploy", "--token", token]
        if self.environment == "production":
            cmd.append("--prod")
            
        if org_id:
            cmd.extend(["--scope", org_id])
            
        run_command(cmd, env=env)
        logger.info("Deploy para o Vercel concluído com sucesso!")

    def _deploy_to_netlify(self, token: Optional[str], site_id: Optional[str]) -> None:
        """Implantar no Netlify usando CLI."""
        logger.info("Iniciando deploy para o Netlify...")
        if not token:
            logger.error("NETLIFY_DEPLOY_TOKEN não fornecido. Não é possível continuar o deploy para Netlify.")
            sys.exit(1)
            
        if not site_id:
            logger.error("NETLIFY_SITE_ID não fornecido.")
            sys.exit(1)
            
        # Instalar Netlify CLI se necessário
        if not shutil.which("netlify"):
            logger.info("Netlify CLI não encontrado. Instalando via npm...")
            run_command(["npm", "install", "-g", "netlify-cli"])
            
        env = {
            "NETLIFY_AUTH_TOKEN": token,
            "NETLIFY_SITE_ID": site_id
        }
        
        cmd = ["netlify", "deploy", "--dir", self.dist_directory]
        if self.environment == "production":
            cmd.append("--prod")
            
        run_command(cmd, env=env)
        logger.info("Deploy para o Netlify concluído com sucesso!")


class AndroidDeployer:
    """Responsável por construir, assinar e implantar o app Android do Player One."""
    
    def __init__(self, environment: str, java_version: str, build_type: str, track: str, package_name: str):
        self.environment = environment
        self.java_version = java_version
        self.build_type = build_type
        self.track = track
        self.package_name = package_name

    def build(self) -> str:
        """Compila o aplicativo e gera o App Bundle (AAB)."""
        logger.info("Iniciando compilação do Android App Bundle (AAB)...")
        
        # Dar permissão de execução ao gradlew
        if os.path.exists("./gradlew"):
            run_command(["chmod", "+x", "./gradlew"])
        else:
            logger.warning("./gradlew não encontrado no diretório atual. Tentando compilar mesmo assim...")
            
        # Escolher tarefa Gradle adequada
        task = "bundleRelease" if self.build_type == "release" else "bundleDebug"
        logger.info(f"Executando gradlew {task}...")
        run_command(["./gradlew", task])
        
        # Encontrar o AAB gerado
        aab_pattern = f"app/build/outputs/bundle/{self.build_type}/app-{self.build_type}.aab"
        aab_files = glob.glob(aab_pattern)
        if not aab_files:
            # Busca recursiva se não estiver no caminho padrão
            aab_files = glob.glob("**/outputs/bundle/**/*.aab", recursive=True)
            
        if not aab_files:
            logger.error("Não foi possível localizar o arquivo .aab gerado.")
            sys.exit(1)
            
        aab_path = aab_files[0]
        logger.info(f"AAB gerado localizado em: {aab_path}")
        return aab_path

    def sign_bundle(self, aab_path: str, keystore_b64: str, keystore_password: str, key_alias: str, key_password: str) -> str:
        """Decodifica a keystore e assina o pacote AAB."""
        logger.info("Iniciando assinatura do Android App Bundle...")
        
        keystore_path = "app/release.jks"
        decode_base64_to_file(keystore_b64, keystore_path)
        
        # Para assinar .aab (Android App Bundle), usamos o jarsigner ou o apksigner do Android SDK.
        # Por padrão, jarsigner é amplamente disponível e recomendado para bundles.
        if shutil.which("jarsigner"):
            logger.info("Usando jarsigner para assinar o App Bundle...")
            cmd = [
                "jarsigner",
                "-verbose",
                "-sigalg", "SHA256withRSA",
                "-digestalg", "SHA-256",
                "-keystore", keystore_path,
                "-storepass", keystore_password,
                "-keypass", key_password,
                aab_path,
                key_alias
            ]
            run_command(cmd)
            logger.info("App Bundle assinado digitalmente com sucesso usando jarsigner!")
        else:
            logger.warning("jarsigner não encontrado no PATH. Tentando usar apksigner...")
            # Alternativa via apksigner (se disponível)
            if shutil.which("apksigner"):
                cmd = [
                    "apksigner", "sign",
                    "--ks", keystore_path,
                    "--ks-pass", f"pass:{keystore_password}",
                    "--ks-key-alias", key_alias,
                    "--key-pass", f"pass:{key_password}",
                    aab_path
                ]
                run_command(cmd)
                logger.info("App Bundle assinado com sucesso usando apksigner!")
            else:
                logger.error("Nem 'jarsigner' nem 'apksigner' foram encontrados. Instale o Java JDK ou Android SDK Tools.")
                sys.exit(1)
                
        return aab_path

    def publish(self, aab_path: str, service_account_json_str: str) -> None:
        """Publica o pacote AAB assinado no console do Google Play Developer API."""
        logger.info(f"Iniciando publicação no Google Play Store (Track: {self.track})...")
        
        # Criar arquivo temporário para as credenciais JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(service_account_json_str)
            json_path = f.name
            
        try:
            # Tentativa de upload usando a biblioteca oficial do Google API Client em Python
            try:
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaFileUpload
                from google.oauth2 import service_account
                
                logger.info("Carregando credenciais da conta de serviço e conectando-se ao Google Play Developer API...")
                scopes = ["https://www.googleapis.com/auth/androidpublisher"]
                credentials = service_account.Credentials.from_service_account_file(json_path, scopes=scopes)
                service = build("androidpublisher", "v3", credentials=credentials)
                
                # 1. Criar uma nova edição (Edit) de publicação
                logger.info("Criando nova transação de edição (Edit)...")
                edit_request = service.edits().insert(body={}, packageName=self.package_name)
                edit_result = edit_request.execute()
                edit_id = edit_result["id"]
                
                # 2. Fazer upload do arquivo AAB
                logger.info(f"Fazendo upload do arquivo AAB ({aab_path})...")
                media = MediaFileUpload(aab_path, mimetype="application/octet-stream", resumable=True)
                upload_request = service.edits().bundles().upload(
                    packageName=self.package_name,
                    editId=edit_id,
                    media_body=media
                )
                
                # Upload com barra de progresso simples
                response = None
                while response is None:
                    status, response = upload_request.next_chunk()
                    if status:
                        logger.info(f"Progresso do upload: {int(status.progress() * 100)}%")
                        
                version_code = response["versionCode"]
                logger.info(f"Upload concluído! Código de versão gerado: {version_code}")
                
                # 3. Vincular o pacote (AAB) ao Track de lançamento (internal, alpha, beta, production)
                logger.info(f"Vinculando o bundle código {version_code} ao canal '{self.track}'...")
                track_body = {
                    "track": self.track,
                    "releases": [{
                        "versionCodes": [str(version_code)],
                        "status": "completed"
                    }]
                }
                service.edits().tracks().update(
                    packageName=self.package_name,
                    editId=edit_id,
                    track=self.track,
                    body=track_body
                ).execute()
                
                # 4. Validar e enviar/commitar as mudanças
                logger.info("Confirmando e aplicando as alterações na Google Play Store...")
                service.edits().commit(packageName=self.package_name, editId=edit_id).execute()
                logger.info(f"Sucesso! Versão {version_code} lançada na track {self.track} com sucesso!")
                
            except ImportError:
                logger.warning("As dependências Python 'google-api-python-client' e 'google-auth' não estão instaladas.")
                logger.info("Tentando encontrar uma ferramenta CLI de upload alternativa (ex: fastlane ou gradle)...")
                # Caso não tenha as bibliotecas Python instaladas, podemos sugerir o comando ou rodar se existir
                if shutil.which("fastlane"):
                    logger.info("Fastlane instalado. Executando deploy via Fastlane...")
                    run_command(["fastlane", "supply", "--aab", aab_path, "--track", self.track, "--package_name", self.package_name, "--json_key", json_path])
                else:
                    logger.error("Bibliotecas 'google-api-python-client' não disponíveis e 'fastlane' não instalado no sistema.")
                    logger.info("Por favor, instale as dependências executando: pip install google-api-python-client google-auth")
                    sys.exit(1)
        finally:
            # Limpar o arquivo de credenciais temporário por motivos de segurança
            if os.path.exists(json_path):
                os.remove(json_path)


class iOSDeployer:
    """Responsável por configurar assinaturas, compilar e implantar o app iOS (Player One iOS)."""
    
    def __init__(self, environment: str, xcode_version: str, scheme: str, workspace_path: str):
        self.environment = environment
        self.xcode_version = xcode_version
        self.scheme = scheme
        self.workspace_path = workspace_path

    def select_xcode(self) -> None:
        """Define a versão correta do Xcode para compilação."""
        logger.info(f"Configurando versão do Xcode para: {self.xcode_version}")
        try:
            # Tentar selecionar versão especificada
            run_command(["sudo", "xcode-select", "-s", f"/Applications/Xcode_{self.xcode_version}.app"])
        except Exception:
            logger.warning(f"Não foi possível definir o Xcode_{self.xcode_version}.app. Usando Xcode padrão do sistema.")

    def setup_signing(self, p12_b64: str, p12_password: str, profile_b64: str) -> str:
        """Decodifica e importa os certificados Apple e perfis de provisionamento de forma nativa no macOS."""
        logger.info("Iniciando configuração de assinaturas e certificados iOS...")
        
        # Caminhos temporários
        runner_temp = tempfile.gettempdir()
        p12_path = os.path.join(runner_temp, "certificate.p12")
        profile_path = os.path.join(runner_temp, "profile.mobileprovision")
        
        decode_base64_to_file(p12_b64, p12_path)
        decode_base64_to_file(profile_b64, profile_path)
        
        # Gerar chaveiro temporário para o runner de automação com senha aleatória para segurança
        keychain_path = os.path.join(runner_temp, "app-signing.keychain-db")
        keychain_password = secrets.token_hex(16)
        
        logger.info("Criando chaveiro temporário...")
        run_command(["security", "create-keychain", "-p", keychain_password, keychain_path])
        run_command(["security", "default-keychain", "-s", keychain_path])
        run_command(["security", "unlock-keychain", "-p", keychain_password, keychain_path])
        run_command(["security", "set-keychain-settings", "-lut", "21600", keychain_path])
        
        # Importar P12 para o chaveiro recém-criado
        logger.info("Importando certificado P12 para o chaveiro...")
        run_command([
            "security", "import", p12_path,
            "-k", keychain_path,
            "-P", p12_password,
            "-T", "/usr/bin/codesign",
            "-T", "/usr/bin/productsign"
        ])
        
        run_command([
            "security", "set-key-partition-list",
            "-S", "apple-tool:,apple:,codesign:",
            "-s", "-k", keychain_password,
            keychain_path
        ])
        
        # Instalar Provisioning Profile no diretório oficial do Xcode
        prov_profiles_dir = os.path.expanduser("~/Library/MobileDevice/Provisioning Profiles")
        os.makedirs(prov_profiles_dir, exist_ok=True)
        shutil.copy(profile_path, prov_profiles_dir)
        logger.info(f"Provisioning Profile copiado para {prov_profiles_dir} com sucesso!")
        
        return keychain_path

    def build_archive(self, archive_path: str) -> None:
        """Executa xcodebuild para gerar o .xcarchive."""
        logger.info(f"Iniciando compilação do Archive (Xcode Scheme: {self.scheme})...")
        
        # Se workspace_path contiver glob, resolve o caminho
        resolved_workspace = self.workspace_path
        if "*" in self.workspace_path:
            matches = glob.glob(self.workspace_path)
            if matches:
                resolved_workspace = matches[0]
                
        cmd = [
            "xcodebuild",
            "-workspace", resolved_workspace,
            "-scheme", self.scheme,
            "-sdk", "iphoneos",
            "-configuration", "Release",
            "-archivePath", archive_path,
            "archive"
        ]
        run_command(cmd)
        logger.info(f"Archive iOS gerado com sucesso em: {archive_path}")

    def export_ipa(self, archive_path: str, export_path: str, team_id: str = "YOUR_TEAM_ID") -> str:
        """Exporta o IPA assinado a partir do Archive gerado usando um ExportOptions.plist gerado dinamicamente."""
        logger.info("Exportando arquivo IPA do Archive...")
        
        runner_temp = tempfile.gettempdir()
        export_options_plist_path = os.path.join(runner_temp, "ExportOptions.plist")
        
        # Estrutura do arquivo ExportOptions.plist
        export_options = {
            "method": "app-store",
            "teamID": team_id,
            "signingStyle": "manual"
        }
        
        # Salvar o Plist usando a biblioteca padrão do Python
        with open(export_options_plist_path, "wb") as f:
            plistlib.dump(export_options, f)
            
        logger.info(f"ExportOptions.plist gerado em: {export_options_plist_path}")
        
        cmd = [
            "xcodebuild",
            "-exportArchive",
            "-archivePath", archive_path,
            "-exportOptionsPlist", export_options_plist_path,
            "-exportPath", export_path
        ]
        run_command(cmd)
        
        # Localizar o arquivo IPA gerado
        ipa_files = glob.glob(os.path.join(export_path, "*.ipa"))
        if not ipa_files:
            logger.error("Nenhum arquivo .ipa encontrado no diretório de exportação.")
            sys.exit(1)
            
        ipa_path = ipa_files[0]
        logger.info(f"Arquivo .ipa localizado com sucesso: {ipa_path}")
        return ipa_path

    def upload_to_testflight(self, ipa_path: str, api_key: str, key_id: str, issuer_id: str) -> None:
        """Faz upload do arquivo IPA final para o App Store Connect (TestFlight)."""
        logger.info("Carregando o IPA para o App Store Connect / TestFlight...")
        
        # Configurar diretório de chaves da Apple obrigatório para altool
        private_keys_dir = os.path.expanduser("~/.appstoreconnect/private_keys")
        os.makedirs(private_keys_dir, exist_ok=True)
        
        key_file_path = os.path.join(private_keys_dir, f"AuthKey_{key_id}.p8")
        with open(key_file_path, "w") as f:
            f.write(api_key)
            
        try:
            logger.info("Iniciando upload de produção usando xcrun altool...")
            cmd = [
                "xcrun", "altool",
                "--upload-app",
                "-f", ipa_path,
                "-t", "ios",
                "--apiKey", key_id,
                "--apiIssuer", issuer_id
            ]
            run_command(cmd)
            logger.info("Upload ao TestFlight concluído com sucesso!")
        finally:
            # Remover chave privada sensível após a operação
            if os.path.exists(key_file_path):
                os.remove(key_file_path)


def main():
    parser = argparse.ArgumentParser(
        description="Lumia Nexus - Central de Automação de CI/CD em Python",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcomandos de implantação disponíveis")
    
    # -------------------------------------------------------------
    # Subcomando Website
    # -------------------------------------------------------------
    web_parser = subparsers.add_parser("website", help="Compilar e implantar o Website Player One")
    web_parser.add_argument("--environment", default="production", choices=["production", "staging"], help="Ambiente de destino")
    web_parser.add_argument("--node-version", default="20", help="Versão do Node.js a utilizar")
    web_parser.add_argument("--build-command", default="npm run build", help="Comando de compilação")
    web_parser.add_argument("--dist-directory", default="dist", help="Diretório de distribuição compilado")
    web_parser.add_argument("--provider", default="github-pages", choices=["github-pages", "vercel", "netlify"], help="Provedor de hospedagem")
    web_parser.add_argument("--token", help="Token de autenticação do provedor (DEPLOY_TOKEN ou GITHUB_TOKEN)")
    web_parser.add_argument("--vercel-org-id", help="Vercel Organization ID")
    web_parser.add_argument("--vercel-project-id", help="Vercel Project ID")
    web_parser.add_argument("--netlify-site-id", help="Netlify Site ID")

    # -------------------------------------------------------------
    # Subcomando Android
    # -------------------------------------------------------------
    android_parser = subparsers.add_parser("android", help="Compilar, assinar e implantar o aplicativo Android")
    android_parser.add_argument("--environment", default="production", choices=["production", "staging"], help="Ambiente de destino")
    android_parser.add_argument("--java-version", default="17", help="Versão do JDK")
    android_parser.add_argument("--build-type", default="release", choices=["release", "debug"], help="Tipo de compilação")
    android_parser.add_argument("--track", default="internal", choices=["internal", "alpha", "beta", "production"], help="Canal da Google Play Store")
    android_parser.add_argument("--package-name", required=True, help="Nome do pacote do aplicativo Android (ex: com.lumianexus.playerone)")
    android_parser.add_argument("--keystore-base64", help="Keystore codificada em Base64")
    android_parser.add_argument("--keystore-password", help="Senha do arquivo Keystore")
    android_parser.add_argument("--key-alias", help="Alias da chave na Keystore")
    android_parser.add_argument("--key-password", help="Senha do alias da chave")
    android_parser.add_argument("--service-account-json", help="Conteúdo texto do arquivo JSON da conta de serviço Google")

    # -------------------------------------------------------------
    # Subcomando iOS
    # -------------------------------------------------------------
    ios_parser = subparsers.add_parser("ios", help="Configurar certificados, compilar e implantar o aplicativo iOS")
    ios_parser.add_argument("--environment", default="production", choices=["production", "staging"], help="Ambiente de destino")
    ios_parser.add_argument("--xcode-version", default="15.2", help="Versão do Xcode")
    ios_parser.add_argument("--scheme", required=True, help="Esquema (Scheme) do Xcode para build")
    ios_parser.add_argument("--workspace-path", default="ios/*.xcworkspace", help="Caminho do arquivo .xcworkspace")
    ios_parser.add_argument("--team-id", default="YOUR_TEAM_ID", help="Team ID da Apple Developer Account")
    ios_parser.add_argument("--p12-base64", help="Certificado de distribuição p12 em Base64")
    ios_parser.add_argument("--p12-password", help="Senha do certificado p12")
    ios_parser.add_argument("--profile-base64", help="Provisioning Profile em Base64")
    ios_parser.add_argument("--api-key", help="Chave privada App Store Connect API (.p8 em texto)")
    ios_parser.add_argument("--key-id", help="App Store Connect API Key ID")
    ios_parser.add_argument("--issuer-id", help="App Store Connect Issuer ID")

    args = parser.parse_args()
    
    # -------------------------------------------------------------
    # Execução do Subcomando Website
    # -------------------------------------------------------------
    if args.command == "website":
        # Fallbacks automáticos para variáveis de ambiente se não fornecido via CLI
        token = args.token or os.environ.get("DEPLOY_TOKEN") or os.environ.get("GITHUB_TOKEN")
        vercel_org_id = args.vercel_org_id or os.environ.get("VERCEL_ORG_ID")
        vercel_project_id = args.vercel_project_id or os.environ.get("VERCEL_PROJECT_ID")
        netlify_site_id = args.netlify_site_id or os.environ.get("NETLIFY_SITE_ID")
        
        deployer = WebsiteDeployer(
            environment=args.environment,
            node_version=args.node_version,
            build_command=args.build_command,
            dist_directory=args.dist_directory,
            provider=args.provider
        )
        
        deployer.build()
        deployer.deploy(
            token=token,
            vercel_org_id=vercel_org_id,
            vercel_project_id=vercel_project_id,
            netlify_site_id=netlify_site_id
        )
        
    # -------------------------------------------------------------
    # Execução do Subcomando Android
    # -------------------------------------------------------------
    elif args.command == "android":
        keystore_b64 = args.keystore_base64 or os.environ.get("KEYSTORE_BASE64")
        keystore_password = args.keystore_password or os.environ.get("KEYSTORE_PASSWORD")
        key_alias = args.key_alias or os.environ.get("KEY_ALIAS")
        key_password = args.key_password or os.environ.get("KEY_PASSWORD")
        service_account_json = args.service_account_json or os.environ.get("PLAY_SERVICE_ACCOUNT_JSON")
        
        if not all([keystore_b64, keystore_password, key_alias, key_password]):
            logger.error("Erro: Credenciais de assinatura (Keystore, alias e senhas) são obrigatórias.")
            sys.exit(1)
            
        deployer = AndroidDeployer(
            environment=args.environment,
            java_version=args.java_version,
            build_type=args.build_type,
            track=args.track,
            package_name=args.package_name
        )
        
        aab_path = deployer.build()
        signed_aab_path = deployer.sign_bundle(
            aab_path=aab_path,
            keystore_b64=keystore_b64,
            keystore_password=keystore_password,
            key_alias=key_alias,
            key_password=key_password
        )
        
        if service_account_json:
            deployer.publish(aab_path=signed_aab_path, service_account_json_str=service_account_json)
        else:
            logger.warning("PLAY_SERVICE_ACCOUNT_JSON não fornecido. O pacote AAB foi compilado e assinado, mas não pôde ser enviado.")
            logger.info(f"Seu pacote assinado está disponível em: {signed_aab_path}")

    # -------------------------------------------------------------
    # Execução do Subcomando iOS
    # -------------------------------------------------------------
    elif args.command == "ios":
        p12_b64 = args.p12_base64 or os.environ.get("P12_KEY_BASE64")
        p12_password = args.p12_password or os.environ.get("P12_PASSWORD")
        profile_b64 = args.profile_base64 or os.environ.get("PROVISION_PROFILE_BASE64")
        api_key = args.api_key or os.environ.get("APP_STORE_CONNECT_API_KEY")
        key_id = args.key_id or os.environ.get("APP_STORE_CONNECT_KEY_ID")
        issuer_id = args.issuer_id or os.environ.get("APP_STORE_CONNECT_ISSUER_ID")
        
        if not all([p12_b64, p12_password, profile_b64]):
            logger.error("Erro: Credenciais do desenvolvedor Apple e Provisioning Profile são obrigatórios.")
            sys.exit(1)
            
        deployer = iOSDeployer(
            environment=args.environment,
            xcode_version=args.xcode_version,
            scheme=args.scheme,
            workspace_path=args.workspace_path
        )
        
        # Executar fluxo iOS
        deployer.select_xcode()
        deployer.setup_signing(p12_b64=p12_b64, p12_password=p12_password, profile_b64=profile_b64)
        
        runner_temp = tempfile.gettempdir()
        archive_path = os.path.join(runner_temp, "project.xcarchive")
        export_path = os.path.join(runner_temp, "build")
        
        deployer.build_archive(archive_path=archive_path)
        ipa_path = deployer.export_ipa(archive_path=archive_path, export_path=export_path, team_id=args.team_id)
        
        if all([api_key, key_id, issuer_id]):
            deployer.upload_to_testflight(ipa_path=ipa_path, api_key=api_key, key_id=key_id, issuer_id=issuer_id)
        else:
            logger.warning("Credenciais da API do App Store Connect não fornecidas. O arquivo IPA foi compilado, mas não pôde ser enviado.")
            logger.info(f"Seu arquivo IPA assinado está disponível em: {ipa_path}")


if __name__ == "__main__":
    main()
