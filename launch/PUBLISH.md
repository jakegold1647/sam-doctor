# Publish SAM Doctor free alpha

This runbook assumes the product has been reviewed locally and you are ready to make the repository public. Do not publish logs, customer failures, AWS credentials, access keys, session tokens, or personal information.

## 1. Choose the public repository

Create an empty public GitHub repository named `sam-doctor` under the account you want customers and employers to see.

Before the first commit, choose the Git email address you want exposed in public commit metadata. Use a GitHub no-reply email if you do not want a personal address public.

```powershell
git config user.name "Your public name"
git config user.email "your-public-git-email"
git add .
git commit -m "Launch SAM Doctor free alpha"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/sam-doctor.git
git push -u origin main
```

## 2. Enable the public alpha

1. Open the repository's Actions tab and confirm the `Verify free core` workflow passes.
2. Create a `v0.1.0` GitHub release with the README's install command and demo command.
3. Replace `YOUR_GITHUB_USERNAME` in `site/index.html` with the public account name.
4. Enable GitHub Pages for the `site/` directory or deploy the static page through another host.

## 3. Prepare the founder checkout

Create a Lemon Squeezy one-time product using `launch/PRODUCT-LISTING.md`.

Do not activate a purchase button until the product description includes the delivery condition and refund terms. Then replace the `YOUR_STORE` and `YOUR_PRODUCT` placeholders in `site/index.html` with the checkout URL.

## 4. First distribution

Use `launch/OUTREACH.md` for personalized conversations with developers who have a recent, public SAM, CloudFormation, IAM, or GitHub Actions error. Lead with the free alpha and ask for a sanitized failure. Ask for founder payment only after the report proves useful.

## Definition of the first revenue milestone

Three $39 founder purchases from people who are not friends or family. Record the buyer type, problem, acquisition channel, and feedback without storing their logs or credentials.

