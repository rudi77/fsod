# Entra-App-Registrierung für MCP-Server (Microsoft 365) hinter dem LiteLLM-Gateway

Diese Anleitung beschreibt **Schritt für Schritt**, wie du in **Microsoft Entra ID** (früher
Azure AD) eine eigene App registrierst, damit der [`@softeria/ms-365-mcp-server`](https://github.com/Softeria/ms-365-mcp-server)
hinter dem LiteLLM-Gateway für **alle Mitarbeiter** funktioniert — jeder mit seinem **eigenen
Postfach**, ohne geteilte Tokens.

> **Warum eine eigene App?** Die eingebaute Softeria-App ist nur für lokale Einzeltests gedacht.
> Für den Firmeneinsatz brauchst du eine eigene Registrierung, weil nur dort **dein Admin** die
> Berechtigungen tenant-weit freigeben (Admin-Consent), die Scopes auf das Nötigste begrenzen und
> Conditional Access / Logging greifen kann.

---

## 0 · Das Identitätsmodell in einem Absatz

- **Authentifizierung (authn)** = *wer bist du* → Microsoft-Login (SSO).
- **Autorisierung (authz)** = *was darfst du* → **delegierte Graph-Scopes** (z. B. `Mail.Read`).
- **Delegiert** (im Namen des angemeldeten Users) ist hier richtig — **nicht** *Application*
  (App-only), denn App-only-`Mail.Read` liest **jedes** Postfach im Tenant.
- Pro Request wird ein **Bearer-Token des Endnutzers** an den ms365-Server gereicht; der ruft
  Graph **als dieser User** auf. Es gibt **kein** geteiltes Token.

---

## 1 · Voraussetzungen

| Was | Detail |
|---|---|
| Entra-ID-Tenant | Eure Firmen-Organisation |
| Rolle zum Registrieren | *Application Administrator* (oder *Application Developer*) |
| Rolle für Admin-Consent | *Global Administrator* oder *Privileged Role Administrator* (tenant-weite Freigabe) |
| Tenant-ID | Portal → *Microsoft Entra ID* → *Overview* → **Tenant ID** (GUID) notieren |

---

## 2 · App registrieren

1. [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations** → **+ New registration**.
2. **Name:** sprechend, z. B. `M365 MCP Gateway – Mail`.
3. **Supported account types:** **Accounts in this organizational directory only (Single tenant)**.
   → Damit ist `MS365_MCP_TENANT_ID` später **eure Tenant-GUID** (nicht `common`).
4. **Redirect URI:** vorerst leer lassen (kommt in Schritt 3, je nach Modus).
5. **Register** klicken.
6. Auf der **Overview**-Seite notieren:
   - **Application (client) ID** → `MS365_MCP_CLIENT_ID`
   - **Directory (tenant) ID** → `MS365_MCP_TENANT_ID`

---

## 3 · Authentifizierungs-Modus wählen (die wichtigste Entscheidung)

Der ms365-Server kennt drei Betriebsarten. **Wähle eine** und konfiguriere die App entsprechend.

| Modus | Wofür | App-Konfiguration |
|---|---|---|
| **A) Device-Code** (`--login`, stdio) | nur lokaler **Einzel**-Test / Bootstrap | *Public client flows* = **Yes**, **kein** Secret |
| **B) HTTP-OAuth** (`--http`) | **Multi-User**, Client macht den OAuth-Login selbst | Plattform + Redirect-URIs der Clients |
| **C) On-Behalf-Of** (`--obo`) | **Multi-User**, **eure App** reicht das User-Token durch | Confidential Client (Secret) + *Expose an API* |

> Für „**jeder in der Firma über das Gateway**" sind **B** oder **C** richtig. **A** ist nur der
> Bootstrap-Hack aus dem Demo (ein geteiltes Token) und **nicht** für mehrere Nutzer geeignet.

### A) Device-Code (nur Einzeltest)
- **Authentication** → **Advanced settings** → **Allow public client flows** → **Yes** → *Save*.
- Kein Redirect-URI, kein Secret nötig.

### B) HTTP-OAuth (empfohlen für interaktive Clients)
Der Server ist ein OAuth-2.1-Resource-Server; MCP-Clients (Claude Desktop, Open WebUI, …) machen
den Login automatisch (Dynamic Client Registration ist im `--http`-Modus an).
- **Authentication** → **+ Add a platform**:
  - **mit** Client-Secret → Plattform **Web**
  - **ohne** Client-Secret (reiner Public Client) → **Mobile and desktop applications**
- **Redirect-URIs** der Clients eintragen, die du nutzt. Beispiele:
  - MCP Inspector (Tests): `http://localhost:6274/oauth/callback` und `http://localhost:6274/oauth/callback/debug`
  - optionaler Server-Callback: `http://localhost:3000/callback`
  - eure echten Client-/Reverse-Proxy-URLs (z. B. `https://mcp.eure-domain.de/callback`)
- Läuft der Server hinter einem Reverse-Proxy: starte ihn mit `--public-url https://mcp.eure-domain.de`,
  damit die Authorize-URL von außen erreichbar ist.

### C) On-Behalf-Of (empfohlen, wenn eine eigene App den User schon eingeloggt hat)
Eure Web-/Agent-App authentifiziert den Mitarbeiter (SSO) und schickt dessen Token an ms365; der
tauscht es per OBO gegen ein Graph-Token.
- **Confidential Client:** Client-Secret oder Zertifikat anlegen (Schritt 5).
- **Expose an API** (Schritt 6) — damit eure App `api://<clientId>/access_as_user` anfordern kann.

---

## 4 · API-Permissions (Microsoft Graph, **delegiert**)

1. **API permissions** → **+ Add a permission** → **Microsoft Graph** → **Delegated permissions**.
2. Mindestens hinzufügen:
   | Scope | Wofür |
   |---|---|
   | `offline_access` | **Refresh-Tokens** (Session überlebt > 1 h) — wichtig! |
   | `User.Read` | Sign-in / Basisprofil |
   | `Mail.Read` | Mails **lesen** |
   | `Mail.Send` | Mails **senden** (nur wenn gewünscht) |
   | `Mail.ReadWrite` | Entwürfe/Ordner/Verschieben (nur wenn gewünscht) |
   | `Mail.Read.Shared` / `Mail.Send.Shared` | **geteilte** Postfächer (nur mit `--org-mode`) |
3. **Grant admin consent for `<euer Tenant>`** klicken (Rolle aus Schritt 1).
   → Danach müssen sich Mitarbeiter **nicht einzeln** durch einen Consent-Dialog klicken.
4. **Exakte** Scope-Liste für eure Flags vorher ermitteln (für die Admin-Freigabe):
   ```bash
   ms-365-mcp-server --org-mode --preset mail --list-permissions
   # zeigt toolPermissions / effectivePermissions -> genau die im Portal freigeben
   ```

> **Least privilege:** Nimm nur, was du wirklich brauchst. „Nur Lesen" = `Mail.Read` + `offline_access`
> + `User.Read`, und den Server mit `--read-only` starten.

---

## 5 · Client-Secret oder Zertifikat (für Modus B-mit-Secret und C)

1. **Certificates & secrets** → **+ New client secret**.
2. Beschreibung + Ablauf (z. B. 6–12 Monate; **Rotation** einplanen).
3. **Value sofort kopieren** (wird nur einmal angezeigt) → `MS365_MCP_CLIENT_SECRET`.
4. **Nicht** im Klartext/Repo ablegen. Besser **Azure Key Vault** (der Server unterstützt
   `MS365_MCP_KEYVAULT_URL` + Managed Identity) oder ein Secret-Store eurer Pipeline.

> Zertifikat statt Secret ist sicherer (kein Ablauf-Geheimnis im Env) — für Produktion bevorzugen.

---

## 6 · Expose an API (nur OBO, Modus C)

1. **Expose an API** → **Application ID URI** setzen → `api://<Application-(client)-ID>`.
2. **+ Add a scope**:
   - **Scope name:** `access_as_user`
   - **Who can consent:** *Admins and users*
   - Anzeige-/Beschreibungstexte ausfüllen → **Add scope**.
3. Eure aufrufende App fordert dann das Token für `api://<clientId>/access_as_user` an; ms365
   (`--obo`) tauscht es On-Behalf-Of gegen das Graph-Token.

---

## 7 · In den ms365-Server einhängen

Setze die Werte als **Umgebungsvariablen** des ms365-Service (nicht in die Args, nicht ins Repo):

```bash
MS365_MCP_CLIENT_ID=<application-client-id>
MS365_MCP_TENANT_ID=<directory-tenant-id>     # GUID (Single-Tenant), NICHT 'common'
MS365_MCP_CLIENT_SECRET=<secret>              # nur Modus B-mit-Secret / C
```

Beispielstart (HTTP-OAuth, nur Mail, nur Lesen, hinter Proxy):
```bash
ms-365-mcp-server --http 3000 --org-mode --preset mail --read-only \
  --public-url https://mcp.eure-domain.de
```
On-Behalf-Of:
```bash
ms-365-mcp-server --http 3000 --org-mode --preset mail --read-only --obo \
  --public-url https://mcp.eure-domain.de
```

> **Wichtig:** Für Produktion läuft ms365 als **dauerhafter HTTP-Service** (eigener Container),
> **nicht** als stdio-Subprozess von LiteLLM. Stdio + geteiltes Token-Volume (wie im Demo) ist
> Single-User und gehört **nicht** in den Mehrbenutzerbetrieb.

---

## 8 · Verifizieren

1. **Scopes prüfen:** `ms-365-mcp-server --org-mode --preset mail --list-permissions`
   → deckt sich die Ausgabe mit dem im Portal Freigegebenen?
2. **Test-Login** mit einem normalen Mitarbeiter-Account (kein Admin) — kommt **kein**
   Consent-Dialog mehr (weil Admin-Consent erteilt)?
3. **Conditional Access:** Greift bei euch MFA/Geräte-Compliance? Dann muss der Login-Pfad das
   erfüllen (Browser-basierte Flows tun das; reine Device-Code-Flows können an CA-Policies
   scheitern).
4. **Über das Gateway** einen echten Mail-Call machen und im LiteLLM-Log/der UI prüfen, dass er
   dem richtigen Key/User zugeordnet ist.

---

## 9 · Härtung / Betrieb

- **Least privilege:** minimale Scopes, `--read-only`, `--preset mail` (statt aller 200+ Tools).
- **Secrets:** Key Vault + Managed Identity, Rotation, kein Secret im Image/Repo.
- **Conditional Access:** App in eure Policies aufnehmen (MFA, Geräte, Standorte).
- **Audit:** LiteLLM-Logging pro Virtual Key + Entra Sign-in-Logs.
- **Token-Lebenszyklus:** `offline_access` für Refresh; pro-User-Tokens sind kurzlebig und liegen
  beim Client / werden per OBO frisch geholt — **kein** geteilter Datei-Cache.

---

## 10 · Mehrere MCP-Server, die Entra ID für Auth/Authz nutzen

Sobald du **mehr als einen** Entra-gestützten MCP-Server hast (z. B. *ms365-mail*, *ms365-admin*,
ein SharePoint-Server, ein internes Custom-API-MCP), stellen sich drei Fragen: **eine App oder
viele?**, **ein Token oder viele?**, **wer macht authz?**

### 10.1 Der Kernpunkt: das **Audience**-Problem
Ein Access-Token gilt immer für **genau eine** Zielressource (`aud`-Claim). Ein Graph-Token
(`aud = graph.microsoft.com`) funktioniert **nur** für Graph. Ein Token für deine Custom-API
funktioniert **nicht** für Graph und umgekehrt. Daraus folgt:

- **Server, die alle dasselbe Backend (Microsoft Graph) ansprechen** (z. B. mehrere ms365-Profile)
  können sich prinzipiell **ein** Graph-Token teilen — aber das Token trägt dann die **Summe**
  aller Scopes (Least-Privilege leidet, größere Blast-Radius).
- **Server mit unterschiedlichen Ressourcen/APIs** brauchen zwingend **je ein eigenes,
  audience-spezifisches Token**. Ein Token lässt sich **nicht** über Ressourcen hinweg
  wiederverwenden.

### 10.2 Empfohlenes Muster: **eine App-Registrierung pro Server/Ressource + Front-Door-OBO**
```
 Mitarbeiter ──1×SSO──► Front-Door-App (Entra)         ← EIN Login für alle
                              │  User-Token (aud = Front-Door)
                              ▼
                       LiteLLM-Gateway (Governance, Virtual Keys, Routing)
                ┌─────────────┼─────────────────────────────┐
                ▼             ▼                              ▼
         ms365-mail        ms365-admin                 custom-api-mcp
         (App A, OBO)      (App B, OBO)                 (App C, OBO)
                │             │                              │
         OBO→Graph(Mail)  OBO→Graph(Admin)            OBO→eigene API
```
- **Pro Server eine eigene Entra-App** (eigener Client-ID, eigene delegierte Scopes, eigene
  „Expose an API"). Vorteile: **least privilege je Server**, saubere Audiences, getrennte
  Secrets/Rotation, getrennter Audit, kleiner Blast-Radius bei Kompromittierung.
- **Eine Front-Door-App** für das **einmalige** User-SSO. Jeder Downstream-Server macht **OBO**
  vom Front-Door-Token auf **seine** Ressource. → Ein Login, N korrekt geschnittene Tokens.
- **Anti-Muster:** *eine* Riesen-App mit allen Scopes für alle Server. Funktioniert nur, solange
  alles Graph ist, und hebelt Least Privilege aus — vermeiden.

### 10.3 Zwei Ebenen von **Authz** (Defense in Depth)
| Ebene | Womit | Kontrolliert |
|---|---|---|
| **Entra** | delegierte Scopes, **App Roles**, Sicherheitsgruppen, Conditional Access | *Darf dieser User überhaupt ein Token für Server X bekommen?* |
| **LiteLLM** | **Virtual Keys** pro User/Team, **MCP-Permission-Management** (welcher Key/Team sieht welchen Server/welche Tools), Rate-Limits, Budgets | *Darf dieser Gateway-Key zu Server X routen?* |

So entscheidet **Entra**, ob jemand ein gültiges Microsoft-Token erhält, und **LiteLLM**, ob der
Gateway-Zugang das überhaupt darf — zwei unabhängige Schranken.
(LiteLLM-Docs: *mcp_control* für Permission-Management, *mcp_oauth*, *mcp_public_internet*.)

### 10.4 Sonderfall App-only / Admin-Server
Server wie `ms-365-admin-mcp-server` nutzen **Application Permissions** (Client-Credentials,
kein User-Kontext) — z. B. für Security-Alerts, Audit-Logs, Service-Health. Das ist ein
**eigenes, eng kontrolliertes** App-Registrierungs-Profil (sehr mächtig, tenant-weit). **Strikt
trennen** von den delegierten User-Servern: eigene App, eigene Rollenfreigabe, nur für
Daemon-/Admin-Szenarien.

### 10.5 Faustregeln
- **Audience entscheidet:** unterschiedliche Ressourcen ⇒ unterschiedliche Apps/Tokens.
- **Pro Server eine App**, least privilege, Admin-Consent, Secret im Key Vault.
- **Front-Door-App + OBO** für ein einziges User-SSO über alle Server.
- **Authz doppelt:** Entra (Token-Erteilung) **und** LiteLLM (Gateway-Routing).
- **App-only strikt isolieren** und nur für Admin-/Daemon-Server.

---

## Glossar

| Begriff | Bedeutung |
|---|---|
| **authn / authz** | Authentifizierung (wer) / Autorisierung (was darfst du) |
| **Delegated permission** | Server handelt **im Namen des angemeldeten Users** (richtig für „eigenes Postfach") |
| **Application permission** | Server handelt **als sich selbst** (App-only, tenant-weit — gefährlich für Mail) |
| **OBO (On-Behalf-Of)** | Token-Tausch: User-Token für App A → Token für Ressource B |
| **Audience (`aud`)** | Zielressource eines Tokens; nicht über Ressourcen hinweg wiederverwendbar |
| **Admin-Consent** | tenant-weite Freigabe der Scopes durch einen Admin (keine Einzel-Dialoge) |
| **DCR** | Dynamic Client Registration — Clients registrieren sich im HTTP-OAuth-Modus selbst |
| **Conditional Access** | Entra-Richtlinien (MFA, Gerät, Standort), die den Login zusätzlich absichern |
