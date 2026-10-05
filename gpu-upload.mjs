// Preserve File names/extensions. handle_file(File) in the shipped SDK turns
// them into nameless Blobs, which Gradio's image File component rejects.
export async function uploadImages(client, endpoint, files) {
  const uploaded = await client.upload_files(endpoint, files);
  if (uploaded.error || uploaded.files?.length !== files.length) {
    throw new Error('사진을 전송하지 못했어요. 잠시 후 다시 시도해주세요.');
  }
  return uploaded.files.map((path, index) => ({ path, orig_name: files[index].name,
    mime_type: files[index].type, meta: { _type: 'gradio.FileData' } }));
}
