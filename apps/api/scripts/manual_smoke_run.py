#!/usr/bin/env python3
"""
ACOG Manual Smoke Test Script.

This script performs a basic end-to-end smoke test of the ACOG API by:
1. Creating a test channel with persona and style guide
2. Creating a test episode for that channel
3. Triggering planning, scripting, and metadata pipeline stages
4. Polling until completion or failure
5. Printing results summary

PREREQUISITES:
- ACOG API must be running at http://localhost:8000
- PostgreSQL and Redis must be running (via Docker Compose)

RUNNING THIS SCRIPT:
    # From the apps/api directory:

    # Option 1: With Poetry (recommended)
    cd /path/to/ACOG/apps/api
    poetry run python scripts/manual_smoke_run.py

    # Option 2: Direct Python (if venv is active)
    python scripts/manual_smoke_run.py

    # Option 3: With Docker (if API is containerized)
    docker exec -it acog-api poetry run python scripts/manual_smoke_run.py

OPTIONAL ARGUMENTS:
    --base-url   API base URL (default: http://localhost:8000)
    --timeout    Max seconds to wait for pipeline (default: 300)
    --verbose    Enable verbose output

EXAMPLE:
    poetry run python scripts/manual_smoke_run.py --verbose --timeout 120
"""

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class SmokeTestConfig:
    """Configuration for smoke test."""

    base_url: str = "http://localhost:8000"
    timeout_seconds: int = 300
    poll_interval_seconds: int = 5
    verbose: bool = False


class SmokeTestRunner:
    """Runs the ACOG smoke test."""

    def __init__(self, config: SmokeTestConfig):
        self.config = config
        self.api_url = f"{config.base_url}/api/v1"
        self.channel_id: str | None = None
        self.episode_id: str | None = None

    def log(self, message: str, verbose_only: bool = False) -> None:
        """Print log message."""
        if verbose_only and not self.config.verbose:
            return
        print(message)

    def request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Make API request and return JSON response."""
        url = f"{self.api_url}{endpoint}"
        self.log(f"  -> {method} {endpoint}", verbose_only=True)

        response = requests.request(
            method=method,
            url=url,
            json=json,
            params=params,
            timeout=30,
        )

        if response.status_code >= 400:
            self.log(f"  <- {response.status_code}: {response.text}")
            response.raise_for_status()

        return response.json()

    def check_health(self) -> bool:
        """Check if API is healthy."""
        self.log("\n[1/6] Checking API health...")
        try:
            result = self.request("GET", "/health")
            # Health endpoint returns status at top level, not wrapped in data
            status = result.get("status", "unknown")
            self.log(f"  API Status: {status}")
            return status == "healthy"
        except Exception as e:
            self.log(f"  ERROR: API health check failed: {e}")
            return False

    def get_or_create_channel(self) -> str:
        """Get or create a test channel using the lookup endpoint."""
        self.log("\n[2/6] Getting or creating test channel...")

        # Fixed slug for idempotent smoke tests
        fixed_slug = "smoke-test-channel"

        # Channel creation data
        create_data = {
            "name": "Smoke Test Channel",
            "description": "A channel created by the smoke test script",
            "niche": "technology",
            "persona": {
                "name": "TestBot",
                "background": "AI assistant specialized in software testing and education",
                "voice": "friendly and informative",
                "values": ["clarity", "accuracy", "helpfulness"],
                "expertise": ["software testing", "code quality", "tutorials"],
            },
            "style_guide": {
                "tone": "conversational",
                "complexity": "intermediate",
                "pacing": "moderate",
                "humor_level": "light",
                "do_rules": ["explain concepts clearly", "use practical examples"],
                "dont_rules": ["use jargon without explanation", "skip important steps"],
            },
            "voice_profile": {
                "provider": "elevenlabs",
                "voice_id": "test-voice-id",
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
            "avatar_profile": {
                "provider": "heygen",
                "avatar_id": "test-avatar-id",
                "background": "office",
                "framing": "medium",
            },
        }

        # Use PUT /channels/lookup for get-or-create pattern
        lookup_data = {
            "identifier": {
                "slug": fixed_slug,
            },
            "create_data": create_data,
        }

        result = self.request("PUT", "/channels/lookup", json=lookup_data)
        channel = result.get("data", {})
        meta = result.get("meta", {})
        self.channel_id = channel.get("id")

        # Log whether channel was created or found
        was_created = meta.get("created", False)
        matched_by = meta.get("matched_by")

        if was_created:
            self.log(f"  Channel CREATED: {self.channel_id}")
        else:
            self.log(f"  Channel FOUND (matched by {matched_by}): {self.channel_id}")

        self.log(f"  Name: {channel.get('name')}")
        self.log(f"  Slug: {channel.get('slug')}")

        return self.channel_id

    def create_episode(self) -> str:
        """Create a test episode."""
        self.log("\n[3/6] Creating test episode...")

        episode_data = {
            "title": f"Smoke Test Episode {int(time.time())}",
            "idea_brief": "A short video explaining why software testing matters. "
                          "Key points: What is software testing? Types of tests "
                          "(unit, integration, e2e). Benefits of testing. "
                          "Target audience: beginner developers.",
            "idea_source": "manual",
            "priority": "high",
            "target_length_minutes": 10,
            "tags": ["testing", "software", "tutorial"],
            "auto_advance": False,
        }

        result = self.request(
            "POST",
            "/episodes",
            json=episode_data,
            params={"channel_id": self.channel_id},
        )
        episode = result.get("data", {})
        self.episode_id = episode.get("id")

        self.log(f"  Episode created: {self.episode_id}")
        self.log(f"  Title: {episode.get('title')}")
        self.log(f"  Status: {episode.get('status')}")

        return self.episode_id

    def trigger_stage(self, stage: str) -> dict[str, Any]:
        """Trigger a pipeline stage."""
        self.log(f"  Triggering stage: {stage}...")

        result = self.request(
            "POST",
            f"/pipeline/episodes/{self.episode_id}/trigger",
            json={"stage": stage},
        )

        job_data = result.get("data", {})
        self.log(f"    Job ID: {job_data.get('job_id')}", verbose_only=True)
        self.log(f"    Status: {job_data.get('status')}", verbose_only=True)

        return job_data

    def run_pipeline_stages(self) -> None:
        """Trigger Stage 1 pipeline (planning -> scripting -> metadata)."""
        self.log("\n[4/6] Running Stage 1 pipeline...")

        try:
            # Use the new run-stage-1 endpoint that runs all stages sequentially
            result = self.request(
                "POST",
                f"/pipeline/episodes/{self.episode_id}/run-stage-1",
            )
            job_data = result.get("data", {})
            self.log(f"  Stage 1 pipeline triggered")
            self.log(f"    Job ID: {job_data.get('job_id')}", verbose_only=True)
            self.log(f"    Celery Task ID: {job_data.get('celery_task_id')}", verbose_only=True)
        except requests.HTTPError as e:
            self.log(f"  Stage 1 pipeline failed to trigger: {e}")
            # Fall back to individual stage triggers
            self.log("  Falling back to individual stage triggers...")
            stages = ["planning", "scripting", "metadata"]
            for stage in stages:
                try:
                    self.trigger_stage(stage)
                    self.log(f"    {stage}: queued")
                except requests.HTTPError as err:
                    self.log(f"    {stage}: failed ({err})")

    def poll_for_completion(self) -> dict[str, Any]:
        """Poll until pipeline reaches target state or times out."""
        self.log("\n[5/6] Polling for completion...")

        target_statuses = {"script_review", "metadata", "audio", "avatar", "broll", "ready", "published"}
        failure_statuses = {"failed", "cancelled"}

        start_time = time.time()
        last_status = None

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.config.timeout_seconds:
                self.log(f"  TIMEOUT after {elapsed:.0f}s")
                break

            # Get episode status
            result = self.request("GET", f"/episodes/{self.episode_id}")
            episode = result.get("data", {})
            current_status = episode.get("status", "unknown")

            if current_status != last_status:
                self.log(f"  [{elapsed:.0f}s] Status: {current_status}")
                last_status = current_status

            # Check for completion
            if current_status in target_statuses:
                self.log(f"  Pipeline reached target status: {current_status}")
                return episode

            # Check for failure
            if current_status in failure_statuses:
                self.log(f"  Pipeline failed with status: {current_status}")
                return episode

            time.sleep(self.config.poll_interval_seconds)

        return episode

    def get_pipeline_status(self) -> dict[str, Any]:
        """Get detailed pipeline status."""
        result = self.request("GET", f"/pipeline/episodes/{self.episode_id}/status")
        return result.get("data", {})

    def get_assets(self) -> list[dict[str, Any]]:
        """Get episode assets."""
        result = self.request("GET", f"/assets/episode/{self.episode_id}")
        return result.get("data", [])

    def print_summary(self, episode: dict[str, Any]) -> None:
        """Print final summary."""
        self.log("\n" + "=" * 60)
        self.log("SMOKE TEST SUMMARY")
        self.log("=" * 60)

        # Episode info
        self.log("\nEPISODE INFO:")
        self.log(f"  ID:        {episode.get('id')}")
        self.log(f"  Title:     {episode.get('title')}")
        self.log(f"  Status:    {episode.get('status')}")
        self.log(f"  Channel:   {self.channel_id}")

        # Pipeline status
        self.log("\nPIPELINE STATUS:")
        try:
            pipeline = self.get_pipeline_status()
            progress = pipeline.get("pipeline_progress", {})
            self.log(f"  Progress:  {progress.get('completed_stages', 0)}/{progress.get('total_stages', 0)} stages")
            self.log(f"  Percent:   {progress.get('percent_complete', 0)}%")

            stages = pipeline.get("stages", {})
            for stage_name, stage_info in stages.items():
                status = stage_info.get("status", "unknown")
                if status != "pending":
                    self.log(f"    - {stage_name}: {status}")
        except Exception as e:
            self.log(f"  (Could not fetch pipeline status: {e})")

        # Assets
        self.log("\nASSETS:")
        try:
            assets = self.get_assets()
            if assets:
                for asset in assets:
                    self.log(f"  - Type: {asset.get('type')}")
                    self.log(f"    URI:  {asset.get('uri', 'N/A')}")
                    self.log(f"    Size: {asset.get('file_size_bytes', 'N/A')} bytes")
            else:
                self.log("  (No assets generated yet)")
        except Exception as e:
            self.log(f"  (Could not fetch assets: {e})")

        self.log("\n" + "=" * 60)

    def cleanup(self) -> None:
        """Clean up test resources (optional)."""
        self.log("\nCLEANUP:", verbose_only=True)
        # Optionally delete test channel and episode
        # For now, leave them for manual inspection
        self.log("  Test resources left for inspection", verbose_only=True)
        self.log(f"  Channel: {self.config.base_url}/api/v1/channels/{self.channel_id}", verbose_only=True)
        self.log(f"  Episode: {self.config.base_url}/api/v1/episodes/{self.episode_id}", verbose_only=True)

    def run(self) -> bool:
        """Run the full smoke test."""
        self.log("=" * 60)
        self.log("ACOG SMOKE TEST")
        self.log(f"API: {self.api_url}")
        self.log("=" * 60)

        try:
            # Step 1: Health check
            if not self.check_health():
                self.log("\nFAILED: API is not healthy")
                return False

            # Step 2: Get or create channel
            self.get_or_create_channel()
            if not self.channel_id:
                self.log("\nFAILED: Could not get or create channel")
                return False

            # Step 3: Create episode
            self.create_episode()
            if not self.episode_id:
                self.log("\nFAILED: Could not create episode")
                return False

            # Step 4: Trigger pipeline stages
            self.run_pipeline_stages()

            # Step 5: Poll for completion
            episode = self.poll_for_completion()

            # Step 6: Print summary
            self.print_summary(episode)

            # Cleanup
            self.cleanup()

            # Return success if we reached at least script_review
            final_status = episode.get("status", "")
            success_statuses = {"script_review", "metadata", "audio", "avatar", "broll", "ready", "published"}
            success = final_status in success_statuses

            self.log(f"\nRESULT: {'PASSED' if success else 'INCOMPLETE'}")
            return success

        except KeyboardInterrupt:
            self.log("\n\nInterrupted by user")
            return False
        except Exception as e:
            self.log(f"\n\nERROR: {e}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ACOG Manual Smoke Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max seconds to wait for pipeline (default: 300)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    config = SmokeTestConfig(
        base_url=args.base_url,
        timeout_seconds=args.timeout,
        verbose=args.verbose,
    )

    runner = SmokeTestRunner(config)
    success = runner.run()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
