from tensorflow.keras.models import load_model
import tensorflow as tf

# Load original model
model = load_model("model.h5")
print("Original model loaded")

# Convert to float16 safely
for layer in model.layers:
    if hasattr(layer, 'dtype'):
        layer._dtype_policy = tf.keras.mixed_precision.Policy('float16')

# Save compressed model
model.save("model_compressed.h5")
print("Compressed model saved as model_compressed.h5")