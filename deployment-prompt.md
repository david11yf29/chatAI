# AI Builder Deployment Prompt

## Background

This experimental feature gives our students an opportunity to showcase their awesome projects. After completing your project, we provide a simple way to check if your repository is deployment-ready directly from Cursor with AI assistance. If it's not ready, the AI will help you make it ready.

This feature helps you:
1. **Check and prepare your repository** - Verify deployment readiness and fix issues with AI assistance
2. **Learn GitHub** - Create an open-source repository that you can add to your resume and share with others
3. **One-click deployment** - Deploy to the `ai-builders.space` platform, making it easy to share your work whether it's for your resume or a tool you want others to use
4. **Understand limitations** - This is an experimental feature with some constraints (see below)

## How to Use

Simply paste the content or URL of this deployment prompt to Cursor. It's also recommended to include the [OpenAPI specification](https://www.ai-builders.com/resources/students-backend/openapi.json) for more detailed API information. The AI will help you:
- Make your repository deployment-ready
- Deploy your service (ask the AI: "Do you want to deploy now?")
- Learn about deployment parameters and requirements
- Understand what's needed for a successful deployment

## Experimental Feature Limitations

- **Free hosting**: Free for 12 months from the first successful deployment
- **Service limit**: Maximum number of services per user (varies by user, default is 2). Check your limit via the Deployment Portal or API.
- **Service management**: To delete a service or extend hosting, contact your instructor

## Technical Requirements

1. **Dockerfile required.** Your repository **must** include a `Dockerfile` in the root directory. The deployment system uses Docker to build and run your application. Your Dockerfile should:
   - Use an appropriate base image (e.g., `python:3.11-slim` for Python apps)
   - Install dependencies efficiently (consider multi-stage builds for smaller images)
   - Expose the port your application listens on (typically via `EXPOSE $PORT` or `EXPOSE 8000`)
   - **Critical**: Start your application using the `PORT` environment variable in the `CMD` instruction. Use shell form (`sh -c`) to ensure environment variable expansion works correctly.
   - Keep the image size reasonable (remember the 256 MB RAM limit)

   **Example Dockerfile for FastAPI:**
   ```dockerfile
   FROM python:3.11-slim
   
   WORKDIR /app
   
   # Install dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # Copy application code
   COPY . .
   
   # Expose port (PORT will be set at runtime by Koyeb)
   EXPOSE 8000
   
   # Start application using PORT environment variable
   # Use shell form (sh -c) to ensure environment variable expansion
   CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
   ```
   
   **Important**: Your application code (e.g., `app.py`) should also read `PORT` from environment variables:
   ```python
   import os
   port = int(os.getenv("PORT", "8000"))
   # Use this port when starting your server
   ```

   **Common mistakes to avoid:**
   - ❌ `CMD ["uvicorn", "app:app", "--port", "8000"]` - Hard-coded port, won't use PORT env var
   - ❌ `CMD uvicorn app:app --port $PORT` - May not expand $PORT correctly in exec form
   - ✅ `CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"` - Correct: uses shell form with default fallback

2. **Single process / single port.** Your FastAPI (or equivalent) service must serve *everything*—API and static files—from a single HTTP server. Build React/Vite assets ahead of time and serve them via `app.mount("/static", StaticFiles(...))` or similar. Do **not** spawn a second web server or background process.

3. **Honor the `PORT` environment variable.** Koyeb sets `PORT` at runtime; your program **must** read and use this environment variable. Your Dockerfile's `CMD` or `ENTRYPOINT` must use this environment variable when starting the server. **Critical**: Use shell form (`sh -c`) in your CMD instruction to ensure the environment variable is properly expanded. Example: `CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"`. Do not hard-code ports. Your application code should also read `PORT` from environment variables (e.g., `os.getenv("PORT", "8000")` in Python) to ensure it works correctly with Koyeb's dynamic port assignment. Default port is **8000**.

4. **Public repositories only.** This feature is experimental and runs on shared infrastructure. Never commit `.env`, API keys, secrets, or production data. Add them to `.gitignore` before pushing.

5. **All changes must be committed and pushed to GitHub.** The deployment system pulls code directly from your GitHub repository. **Before deploying**, ensure all your changes (including Dockerfile, code updates, configuration files) are committed and pushed to the repository. Uncommitted or unpushed changes will not be included in the deployment. Use `git add .`, `git commit -m "your message"`, and `git push` to ensure your latest code is available.

6. **`AI_BUILDER_TOKEN` is injected for you.** During deployment, we set an environment variable named `AI_BUILDER_TOKEN` to the same platform API key you used when calling `POST /v1/deployments`. Read it at runtime if your app needs to call the Space backend. **Important**: For security reasons, you should not check this token into your repository, and you **do not need to add it to `env_vars`** in your deployment command.

7. **Resource limits.** Instances use nano-sized containers with **256 MB RAM**. Keep dependencies lean, avoid background workers, and free memory when possible. Optimize your Dockerfile to reduce image size and memory footprint.

8. **Need other API keys?** Since most of our teaching scenarios only require the AI Builder token (a unified token that allows you to call many backend services), we inject `AI_BUILDER_TOKEN` automatically. However, if you have other requirements (e.g., you want to use your own OpenAI API key), contact your instructor and we'll help you set it up.

9. **Be patient and monitor.** Provisioning takes 5–10 minutes. Use the Deployment Portal (read-only) or the API to check status. If the state is stuck on "deploying" for more than 20 minutes, review your repository, then share the logs with the instructors.

## Your Task (for AI Assistants)

When a user shares this deployment prompt, follow this conversational playbook:

### Step 1: Initial Research and Intent Discovery

If the user simply pastes this prompt without additional context, start by:

1. **Research the current repository** - Examine the codebase to understand:
   - What type of project it is (FastAPI, Flask, etc.)
   - Whether a Dockerfile exists and is properly configured
   - Current deployment readiness status
   - What needs to be fixed or prepared

2. **Proactively ask about intent** - After your research, engage the user with:
   - "Are you looking to deploy your project? I can help you prepare your repository and deploy it to the `ai-builders.space` platform."
   - "I've reviewed your repository and found [summary of findings]. Would you like me to help you deploy it?"

### Step 2: Deployment Information Gathering

If the user confirms they want to deploy, clearly explain what information you need:

**Critical Information Required (three items):**
- **GitHub Repository URL** - The public repository URL (e.g., `https://github.com/username/repo-name`)
- **Service Name** - A unique name for your deployed service (e.g., `my-awesome-project`). This will become your deployment's subdomain: `https://{service-name}.ai-builders.space`
- **Git Branch** - The Git branch to deploy (e.g., `main`, `master`, `develop`). **This is required** - you must specify which branch contains the code you want to deploy.

**Important clarifications:**
- **Do NOT ask for API endpoint addresses** - The deployment API endpoint is provided by the platform and you will use it automatically. Students do not need to provide this.
- **Do NOT ask for deployment platform credentials** - Students use their existing platform API key (the same one they use for other Space features). Authentication is handled automatically when they call the deployment API.
- **Do NOT ask for port numbers unless specified by the user** - The platform defaults to port **8000**. Your application must honor the `PORT` environment variable set by Koyeb at runtime. The port configuration is handled automatically. If the user's application requires a non-standard port and cannot honor the `PORT` environment variable, only then ask for it.
- **The service name IS the deployment identifier** - The service name uniquely identifies the deployment and becomes part of the public URL. No additional endpoint information is needed.

**Optional but Helpful:**
- Any specific deployment requirements or preferences
- Whether they need help setting up the GitHub repository first

**Example conversation flow:**
```
AI: "Great! To deploy your service, I'll need three pieces of information:
     1. Your GitHub repository URL (e.g., https://github.com/username/repo-name)
     2. A service name for your deployment (e.g., my-awesome-project)
     3. The Git branch to deploy (e.g., main, master, develop)
     
     The service name will become your deployment's subdomain: https://my-awesome-project.ai-builders.space
     
     Do you have these ready, or would you like me to help you set up the GitHub repository first?"
```

### Step 3: Repository Preparation

Before deployment, ensure the repository meets all technical requirements:

1. **Check deployment readiness** - Verify all requirements from the "Technical Requirements" section, including:
   - Presence of a Dockerfile in the repository root
   - Dockerfile's `CMD` instruction uses shell form (`sh -c`) to properly expand the PORT environment variable
   - Dockerfile correctly exposes port and uses `${PORT:-8000}` syntax in CMD
   - **Application code reads PORT from environment variables** - Your application must read `PORT` from `os.getenv("PORT")` or equivalent, not hard-code port numbers
   - Static files are served from the same process (if applicable)
2. **Test Dockerfile (optional, non-blocking)** - **Recommended but optional**: If Docker is available in your environment, suggest testing the Dockerfile build before deployment to catch potential issues early. You can test by running:
   ```bash
   docker build -t test-image .
   docker run -p 8000:8000 -e PORT=8000 test-image
   ```
   **Important**: This is a suggestion only. If Docker is not available in the user's environment, do not block deployment. Simply note that the Dockerfile will be tested during the actual deployment process, and remind the user that this step was skipped. The deployment will proceed regardless of whether local Docker testing was performed.
3. **Fix issues proactively** - Offer to fix any problems you find (e.g., missing Dockerfile, hardcoded ports in CMD or application code, CMD using exec form instead of shell form, missing static file serving, Dockerfile not using PORT environment variable correctly, application code not reading PORT from environment variables)
4. **Explain changes** - When making changes, explain what you're doing and why (e.g., "I'm creating a Dockerfile that uses Python 3.11, installs your dependencies, and starts your FastAPI app using `CMD sh -c 'uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'` to ensure the PORT environment variable is properly expanded. I'm also updating your application code to read `PORT` from `os.getenv('PORT', '8000')` instead of hard-coding the port number.")
5. **Remind to commit and push** - **Critical**: After making any changes to prepare the repository, remind the user that they must commit and push their changes to GitHub before deployment can proceed. The deployment system pulls code directly from the GitHub repository, so all changes must be pushed. Example: "I've made the necessary changes to your repository. Before we can deploy, please commit and push these changes to GitHub using: `git add .`, `git commit -m 'Prepare for deployment'`, and `git push`. Once your changes are pushed, let me know and we can proceed with the deployment."

### Step 4: Deployment Assistance

Once you have the required information and the repository is ready (and changes are committed and pushed to GitHub):

1. **Verify changes are pushed** - Before proceeding, confirm that the user has committed and pushed all changes to GitHub. The deployment system pulls code from the GitHub repository, so any uncommitted or unpushed changes will not be included in the deployment.
2. **Explain the deployment process** - Walk the user through what will happen: you will call the deployment API (`POST /v1/deployments`) with the GitHub repository URL, service name, and Git branch they provided. The system will then clone the specified branch from GitHub, build the Docker image using the Dockerfile, and deploy it to Koyeb. The deployment API endpoint is already known and will be used automatically - students only need to provide the repository URL, service name, and branch name.
3. **Reference the OpenAPI spec** - Use the [OpenAPI specification](https://www.ai-builders.com/resources/students-backend/openapi.json) for detailed API request/response formats. **Note**: This is for reference only - you don't need to ask the user for the API endpoint address, as it's part of the platform infrastructure.
4. **Offer to deploy** - Ask: "Would you like me to proceed with the deployment now?"
5. **Monitor and guide** - Explain that provisioning takes 5-10 minutes and how to check status
6. **Explain streaming logs in the deploy response** - The deploy API response includes deployment status plus `streaming_logs`, which reflect the build status captured during a blocking window (default 60 seconds; configurable via `streaming_log_timeout_seconds`). If `streaming_logs` is empty, double-check the GitHub repo URL and branch. If logs exist, review them for build errors. If logs start OK and then fail later (or are incomplete), use `GET /v1/deployments/{service_name}/logs` to pull more build/runtime logs for deeper debugging.

### Conversation Best Practices

- **Be proactive** - Don't wait for the user to ask; guide them through the process
- **Be clear** - Explicitly state what information you need and why
- **Be educational** - Explain deployment concepts and requirements as you go
- **Be conversational** - Use natural language, not just technical checklists
- **Do NOT ask for information that's not needed** - Only ask for the GitHub repository URL, service name, and Git branch. Do not ask for API endpoint addresses, deployment platform credentials, port numbers, or other infrastructure details. The deployment API endpoint is part of the platform and will be used automatically. Students authenticate using their existing platform API key, which is handled automatically. Port configuration is handled by Koyeb through the PORT environment variable.

## Support

Reach out to the instructors with your service name, repo URL, and the timestamp of the failed deployment.
