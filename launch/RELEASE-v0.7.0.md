# SAM Doctor v0.7.0

SAM Doctor v0.7.0 extends the evidence-first catalog with five direct service
errors drawn from sanitized public deployment reports.

## Highlights

- Detects invalid SAM property keys and IAM role trust policies that contain a
  prohibited `Resource` field.
- Detects Lambda container-image/code-signing incompatibility and invalid S3
  bucket names.
- Detects the S3 `GetObject` denial that prevents CloudFormation from creating a
  Lambda layer from its artifact.

Each report keeps the scope narrow: it identifies the service error and provides
safe verification steps, without accessing AWS or changing a resource.
