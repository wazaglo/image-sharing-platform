.PHONY: help lint test clean tf-init tf-plan tf-apply tf-destroy upload-frontend invalidate-cache

help:
	@grep -E '^[a-zA-Z_-]+:.*$$' $(MAKEFILE_LIST) | sort

tf-init:
	terraform -chdir=terraform init -backend=false

tf-plan:
	terraform -chdir=terraform plan -var-file=environments/$(or $(env),dev)/terraform.tfvars -out plan.tfplan

tf-apply:
	terraform -chdir=terraform apply plan.tfplan

tf-destroy:
	terraform -chdir=terraform destroy -var-file=environments/$(or $(env),dev)/terraform.tfvars

lint:
	cd terraform && terraform fmt -check && terraform validate

test:
	cd tests && python -m pytest -v

clean:
	rm -rf **/__pycache__ **/.pytest_cache **/*.egg-info **/*.zip terraform/.terraform terraform/lambda-zips/*.zip
	find . -name '*.pyc' -delete

upload-frontend:
	aws s3 sync src/frontend/ui/ s3://$$BUCKET/ui/ --cache-control 'max-age=3600'

invalidate-cache:
	aws cloudfront create-invalidation --distribution-id $$DISTRIBUTION_ID --paths '/ui/*'
