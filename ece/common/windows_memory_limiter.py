# ece/common/windows_memory_limiter.py
import sys
import warnings

# This module is Windows-specific.
if sys.platform != 'win32':

    def apply_memory_limit(memory_limit_mb):
        warnings.warn("Memory limiting is only supported on Windows.")

else:
    import win32api
    import win32job
    import winerror

    g_hjob = None

    def _create_job(job_name='', breakaway='silent'):
        hjob = win32job.CreateJobObject(None, job_name)
        if breakaway:
            info = win32job.QueryInformationJobObject(hjob, win32job.JobObjectExtendedLimitInformation)
            if breakaway == 'silent':
                info['BasicLimitInformation']['LimitFlags'] |= (
                    win32job.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)
            else:
                info['BasicLimitInformation']['LimitFlags'] |= (
                    win32job.JOB_OBJECT_LIMIT_BREAKAWAY_OK)
            win32job.SetInformationJobObject(hjob, win32job.JobObjectExtendedLimitInformation, info)
        return hjob

    def _assign_job(hjob):
        global g_hjob
        hprocess = win32api.GetCurrentProcess()
        try:
            win32job.AssignProcessToJobObject(hjob, hprocess)
            g_hjob = hjob
            return True
        except win32job.error as e:
            # ERROR_ACCESS_DENIED can happen if the process is already in a job.
            # Nested jobs are not supported before Windows 8.
            if (e.winerror != winerror.ERROR_ACCESS_DENIED or \
                sys.getwindowsversion() >= (6, 2) or \
                not win32job.IsProcessInJob(hprocess, None)):
                warnings.warn(f'Failed to assign process to job object: {e}')
            return False

    def _limit_memory(memory_limit_bytes):
        if g_hjob is None:
            return
        info = win32job.QueryInformationJobObject(g_hjob, win32job.JobObjectExtendedLimitInformation)
        info['ProcessMemoryLimit'] = memory_limit_bytes
        info['BasicLimitInformation']['LimitFlags'] |= (
            win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY)
        win32job.SetInformationJobObject(g_hjob, win32job.JobObjectExtendedLimitInformation, info)

    def apply_memory_limit(memory_limit_mb):
        """
        Applies a memory limit to the current process using Windows Job Objects.
        This function should be called at the beginning of the application's lifecycle.

        Args:
            memory_limit_mb (int): The memory limit in megabytes.
        """
        if not isinstance(memory_limit_mb, (int, float)) or memory_limit_mb <= 0:
            warnings.warn(f"Invalid memory limit specified: {memory_limit_mb}. Must be a positive number.")
            return

        job = _create_job()
        if _assign_job(job):
            memory_limit_bytes = int(memory_limit_mb * 1024 * 1024)
            _limit_memory(memory_limit_bytes)
            print(f"Successfully applied memory limit of {memory_limit_mb} MB to the current process.")

if __name__ == '__main__':
    # Example usage:
    if sys.platform == 'win32':
        # Set a 100MB memory limit
        apply_memory_limit(100)

        print("Attempting to allocate a large amount of memory...")
        try:
            # This allocation should fail if the limit is effective
            large_data = bytearray(101 * 1024 * 1024)
            print("Memory allocation succeeded (this should not happen if the limit is effective).")
        except MemoryError:
            print("Successfully caught MemoryError. The memory limit is working as expected.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    else:
        print("This example is for Windows only.")
