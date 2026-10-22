from pydantic import BaseModel, Field, model_validator


class DependencyCreate(BaseModel):
    depends_on_task_id: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_dependency(self):
        if self.depends_on_task_id <= 0:
            raise ValueError("Dependency task ID must be positive.")

        return self