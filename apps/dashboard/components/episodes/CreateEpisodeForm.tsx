"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input, Textarea, Select, type SelectOption } from "@/components/ui/Input";
import { Modal, ModalFooter } from "@/components/ui/Modal";
import { Alert } from "@/components/ui/Alert";
import { api, isApiError } from "@/lib/api";
import type { Priority } from "@/lib/types";

interface CreateEpisodeFormProps {
  channelId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface FormData {
  title: string;
  ideaBrief: string;
  priority: Priority;
}

const priorityOptions: SelectOption[] = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

export function CreateEpisodeForm({
  channelId,
  isOpen,
  onClose,
  onSuccess,
}: CreateEpisodeFormProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<FormData>({
    title: "",
    ideaBrief: "",
    priority: "normal",
  });

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.title.trim()) {
      setError("Episode title is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await api.createEpisode(channelId, {
        title: formData.title.trim(),
        idea_brief: formData.ideaBrief.trim() || undefined,
        priority: formData.priority,
      });

      // Close modal
      handleClose();

      // Callback to refresh list
      onSuccess?.();

      // Navigate to the new episode
      router.push(`/episodes/${response.data.id}`);
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message);
      } else {
        setError("Failed to create episode. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setFormData({
        title: "",
        ideaBrief: "",
        priority: "normal",
      });
      setError(null);
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Episode"
      description="Start a new episode with an idea that will go through the content pipeline."
      size="md"
    >
      <form onSubmit={handleSubmit}>
        {error && (
          <Alert variant="error" className="mb-4" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}

        <div className="space-y-4">
          <Input
            label="Episode Title"
            name="title"
            placeholder="e.g., How AI is Transforming Healthcare"
            value={formData.title}
            onChange={(e) => handleChange("title", e.target.value)}
            required
            disabled={isSubmitting}
          />

          <Textarea
            label="Idea Brief"
            name="ideaBrief"
            placeholder="Describe the main topic, key points to cover, and any specific angles or perspectives..."
            value={formData.ideaBrief}
            onChange={(e) => handleChange("ideaBrief", e.target.value)}
            rows={4}
            hint="This will guide the AI planning and script generation"
            disabled={isSubmitting}
          />

          <Select
            label="Priority"
            name="priority"
            options={priorityOptions}
            value={formData.priority}
            onChange={(value) => handleChange("priority", value as Priority)}
            hint="Higher priority episodes are processed first"
            disabled={isSubmitting}
          />
        </div>

        <ModalFooter className="-mx-6 -mb-4 mt-6">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button type="submit" loading={isSubmitting}>
            Create Episode
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
