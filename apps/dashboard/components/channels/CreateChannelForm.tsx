"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Modal, ModalFooter } from "@/components/ui/Modal";
import { Alert } from "@/components/ui/Alert";
import { api, isApiError } from "@/lib/api";
import { useChannels } from "@/hooks/useChannels";

interface CreateChannelFormProps {
  isOpen: boolean;
  onClose: () => void;
}

interface FormData {
  name: string;
  description: string;
  niche: string;
  personaName: string;
  personaBackground: string;
}

export function CreateChannelForm({ isOpen, onClose }: CreateChannelFormProps) {
  const router = useRouter();
  const { mutate } = useChannels();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<FormData>({
    name: "",
    description: "",
    niche: "",
    personaName: "",
    personaBackground: "",
  });

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.name.trim()) {
      setError("Channel name is required");
      return;
    }
    if (!formData.personaName.trim()) {
      setError("Persona name is required");
      return;
    }
    if (!formData.personaBackground.trim()) {
      setError("Persona background is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await api.createChannel({
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        niche: formData.niche.trim() || undefined,
        persona: {
          name: formData.personaName.trim(),
          background: formData.personaBackground.trim(),
        },
      });

      // Refresh the channel list
      await mutate();

      // Close modal and navigate to the new channel
      onClose();
      router.push(`/channels/${response.data.id}`);
    } catch (err) {
      if (isApiError(err)) {
        setError(err.message);
      } else {
        setError("Failed to create channel. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setFormData({
        name: "",
        description: "",
        niche: "",
        personaName: "",
        personaBackground: "",
      });
      setError(null);
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Channel"
      description="Set up a new content channel with its persona and configuration."
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        {error && (
          <Alert variant="error" className="mb-4" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}

        <div className="space-y-4">
          {/* Channel Info Section */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-700 border-b border-gray-200 pb-2">
              Channel Information
            </h3>

            <Input
              label="Channel Name"
              name="name"
              placeholder="e.g., TechExplained"
              value={formData.name}
              onChange={(e) => handleChange("name", e.target.value)}
              required
              disabled={isSubmitting}
            />

            <Textarea
              label="Description"
              name="description"
              placeholder="Brief description of the channel's focus and content..."
              value={formData.description}
              onChange={(e) => handleChange("description", e.target.value)}
              rows={2}
              disabled={isSubmitting}
            />

            <Input
              label="Niche"
              name="niche"
              placeholder="e.g., Technology, Finance, Health"
              value={formData.niche}
              onChange={(e) => handleChange("niche", e.target.value)}
              hint="The content category or niche for this channel"
              disabled={isSubmitting}
            />
          </div>

          {/* Persona Section */}
          <div className="space-y-4 pt-4">
            <h3 className="text-sm font-medium text-gray-700 border-b border-gray-200 pb-2">
              AI Persona
            </h3>

            <Input
              label="Persona Name"
              name="personaName"
              placeholder="e.g., Alex Chen"
              value={formData.personaName}
              onChange={(e) => handleChange("personaName", e.target.value)}
              required
              hint="The name of the AI persona that will present content"
              disabled={isSubmitting}
            />

            <Textarea
              label="Persona Background"
              name="personaBackground"
              placeholder="A tech enthusiast with 10 years of experience in software development. Known for making complex topics accessible and engaging..."
              value={formData.personaBackground}
              onChange={(e) => handleChange("personaBackground", e.target.value)}
              rows={3}
              required
              hint="Describe the persona's expertise, personality, and speaking style"
              disabled={isSubmitting}
            />
          </div>
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
            Create Channel
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
