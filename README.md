# Lumia Nexus - GitHub Actions CI/CD Centralizado 🚀

Este repositório centraliza as ferramentas, configurações e os fluxos de trabalho (Reusable Workflows) de Integração e Entrega Contínuas (CI/CD) para os projetos da Lumia Nexus, incluindo o **Player One** (site e aplicativos móveis).

---

## 📋 Sumário de Workflows Disponíveis

Oferecemos fluxos de trabalho reutilizáveis para facilitar e padronizar o build e o deploy dos projetos da organização. Qualquer repositório sob a organização `cdrluminianexus-droid` pode chamá-los diretamente em seus arquivos de workflow locais.

1. [Implantar Website (`deploy-website.yml`)](#1-implantar-website-deploy-websiteyml)
2. [Implantar Aplicativo Android (`deploy-android.yml`)](#2-implantar-aplicativo-android-deploy-androidyml)
3. [Implantar Aplicativo iOS / Apple TV (`deploy-ios.yml`)](#3-implantar-aplicativo-ios--apple-tv-deploy-iosyml)

---

## 1. Implantar Website (`deploy-website.yml`)

Permite compilar e implantar o site do **Player One** em provedores como **GitHub Pages**, **Vercel** ou **Netlify**.

### Exemplo de Uso no seu Repositório do Site:

```yaml
name: Deploy Website do Player One

on:
  push:
    branches:
      - main

jobs:
  release:
    uses: cdrluminianexus-droid/.github/.github/workflows/deploy-website.yml@main
    with:
      provider: 'github-pages' # Opções: github-pages, vercel, netlify
      node-version: '20'
      build-command: 'npm run build'
      dist-directory: 'dist'
    secrets:
      DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }} # Necessário para Vercel/Netlify
```

---

## 2. Implantar Aplicativo Android (`deploy-android.yml`)

Compila, assina digitalmente o aplicativo Android do **Player One** e publica o pacote (`.aab`) diretamente no Google Play Console para testes ou produção.

### Segredos do Repositório Necessários:
*   `KEYSTORE_BASE64`: O arquivo `.jks` codificado em base64.
*   `KEYSTORE_PASSWORD`: Senha do Keystore.
*   `KEY_ALIAS`: Alias do Keystore.
*   `KEY_PASSWORD`: Senha da chave.
*   `PLAY_SERVICE_ACCOUNT_JSON`: Credenciais JSON da conta de serviço do Google Play Console.

### Exemplo de Uso no seu Repositório Android:

```yaml
name: Deploy Android do Player One

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    uses: cdrluminianexus-droid/.github/.github/workflows/deploy-android.yml@main
    with:
      environment: 'production'
      java-version: '17'
      track: 'internal' # Opções: internal, alpha, beta, production
      package-name: 'com.lumianexus.playerone'
    secrets:
      KEYSTORE_BASE64: ${{ secrets.KEYSTORE_BASE64 }}
      KEYSTORE_PASSWORD: ${{ secrets.KEYSTORE_PASSWORD }}
      KEY_ALIAS: ${{ secrets.KEY_ALIAS }}
      KEY_PASSWORD: ${{ secrets.KEY_PASSWORD }}
      PLAY_SERVICE_ACCOUNT_JSON: ${{ secrets.PLAY_SERVICE_ACCOUNT_JSON }}
```

---

## 3. Implantar Aplicativo iOS / Apple TV (`deploy-ios.yml`)

Compila o aplicativo móvel ou para Apple TV do **Player One**, realiza a assinatura de código nativa do macOS e envia a versão automaticamente para testes no **TestFlight / App Store Connect**.

### Segredos do Repositório Necessários:
*   `P12_KEY_BASE64`: Certificado de distribuição iOS `.p12` codificado em base64.
*   `P12_PASSWORD`: Senha do certificado `.p12`.
*   `PROVISION_PROFILE_BASE64`: Perfil de provisionamento `.mobileprovision` em base64.
*   `APP_STORE_CONNECT_API_KEY`: Conteúdo do arquivo de chave privada `.p8` para acesso à API do App Store Connect.
*   `APP_STORE_CONNECT_KEY_ID`: ID da chave de API do App Store Connect.
*   `APP_STORE_CONNECT_ISSUER_ID`: ID do emissor do App Store Connect.

### Exemplo de Uso no seu Repositório iOS:

```yaml
name: Deploy iOS do Player One

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    uses: cdrluminianexus-droid/.github/.github/workflows/deploy-ios.yml@main
    with:
      environment: 'production'
      xcode-version: '15.2'
      scheme: 'PlayerOne'
      workspace-path: 'ios/PlayerOne.xcworkspace'
    secrets:
      P12_KEY_BASE64: ${{ secrets.P12_KEY_BASE64 }}
      P12_PASSWORD: ${{ secrets.P12_PASSWORD }}
      PROVISION_PROFILE_BASE64: ${{ secrets.PROVISION_PROFILE_BASE64 }}
      APP_STORE_CONNECT_API_KEY: ${{ secrets.APP_STORE_CONNECT_API_KEY }}
      APP_STORE_CONNECT_KEY_ID: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
      APP_STORE_CONNECT_ISSUER_ID: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
```

---

## 🔒 Segurança de Credenciais

Nunca exponha chaves ou senhas em texto puro no código-fonte. Utilize sempre o painel de **Secrets and Variables** de cada repositório no GitHub para manter as chaves de assinatura do Google Play e da Apple totalmente protegidas.